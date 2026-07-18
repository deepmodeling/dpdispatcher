"""Safely extract archives received from remote execution backends."""

import ntpath
import os
import pathlib
import shutil
import stat
import tarfile
import tempfile
import unicodedata
import zipfile
from typing import Any, Dict, Iterable, List, NamedTuple, Tuple


class UnsafeArchiveError(ValueError):
    """Raised when an archive member could create an unsafe filesystem entry."""


class _ValidatedMember(NamedTuple):
    """Archive member metadata that has passed manifest validation."""

    source: Any
    parts: Tuple[str, ...]
    is_directory: bool
    mode: int


_WINDOWS_RESERVED_NAMES = {
    "aux",
    "con",
    "nul",
    "prn",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}
_WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT = 0x400
_WINDOWS_INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF


def _is_windows_reparse_point(path: str) -> bool:
    """Return whether an existing Windows path is a junction/reparse point.

    Python 3.7 ``lstat`` can follow directory junctions, so checking the native
    file attribute is required for every supported Windows version.
    """
    if os.name != "nt":
        return False

    import ctypes

    get_file_attributes = getattr(ctypes, "windll").kernel32.GetFileAttributesW
    get_file_attributes.argtypes = [ctypes.c_wchar_p]
    get_file_attributes.restype = ctypes.c_uint32
    attributes = get_file_attributes(path)
    if attributes == _WINDOWS_INVALID_FILE_ATTRIBUTES:
        raise getattr(ctypes, "WinError")()
    return bool(attributes & _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT)


def _is_unsafe_link(path: str, path_stat: os.stat_result) -> bool:
    """Return whether a path can redirect extraction through a link object."""
    return stat.S_ISLNK(path_stat.st_mode) or _is_windows_reparse_point(path)


def _canonical_member_parts(member_name: str, is_directory: bool) -> Tuple[str, ...]:
    """Return a portable relative path for an archive member.

    Result archives can be produced and consumed on different operating
    systems.  Treating both slash styles as separators and rejecting Windows
    device/alternate-stream spellings prevents names that are harmless on one
    platform from escaping or colliding on another.
    """
    if not member_name or "\x00" in member_name:
        raise UnsafeArchiveError(
            f"Archive member has an invalid empty or NUL-containing name: {member_name!r}"
        )

    portable_name = member_name.replace("\\", "/")
    member_path = pathlib.PurePosixPath(portable_name)
    drive, _ = ntpath.splitdrive(member_name)
    if member_path.is_absolute() or drive or ntpath.isabs(member_name):
        raise UnsafeArchiveError(
            f"Archive member uses an absolute path: {member_name!r}"
        )

    parts: List[str] = []
    for part in portable_name.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise UnsafeArchiveError(
                "Archive member traverses outside the output directory: "
                f"{member_name!r}"
            )
        if ":" in part or part.endswith((" ", ".")):
            raise UnsafeArchiveError(
                f"Archive member uses an unsafe Windows path component: {member_name!r}"
            )
        device_name = part.split(".", 1)[0].casefold()
        if device_name in _WINDOWS_RESERVED_NAMES:
            raise UnsafeArchiveError(
                f"Archive member uses a reserved Windows name: {member_name!r}"
            )
        parts.append(part)

    if not parts and not is_directory:
        raise UnsafeArchiveError(
            f"Archive file member has no output path: {member_name!r}"
        )
    return tuple(parts)


def _validate_manifest(
    candidates: Iterable[Tuple[Any, str, bool, int]],
) -> List[_ValidatedMember]:
    """Validate all members before extraction writes any output."""
    validated: List[_ValidatedMember] = []
    path_types: Dict[str, bool] = {}

    for source, name, is_directory, mode in candidates:
        parts = _canonical_member_parts(name, is_directory)
        canonical_path = "/".join(parts)
        # Case folding is intentionally conservative so one manifest behaves
        # consistently on case-sensitive and case-insensitive filesystems.
        path_key = unicodedata.normalize("NFC", canonical_path).casefold()
        if path_key in path_types:
            raise UnsafeArchiveError(
                f"Archive contains duplicate output path: {canonical_path!r}"
            )

        for index in range(1, len(parts)):
            parent_key = unicodedata.normalize(
                "NFC", "/".join(parts[:index])
            ).casefold()
            if path_types.get(parent_key) is False:
                raise UnsafeArchiveError(
                    "Archive file conflicts with a descendant member: "
                    f"{canonical_path!r}"
                )

        if not is_directory:
            descendant_prefix = path_key + "/"
            if any(key.startswith(descendant_prefix) for key in path_types):
                raise UnsafeArchiveError(
                    "Archive file conflicts with an existing directory member: "
                    f"{canonical_path!r}"
                )

        path_types[path_key] = is_directory
        validated.append(_ValidatedMember(source, parts, is_directory, mode))

    return validated


def _prepare_root(destination: str) -> str:
    """Create and resolve the trusted extraction root."""
    os.makedirs(destination, exist_ok=True)
    root = os.path.realpath(os.path.abspath(destination))
    if not os.path.isdir(root):
        raise UnsafeArchiveError(
            f"Archive extraction destination is not a directory: {destination!r}"
        )
    return root


def _ensure_directory(root: str, parts: Tuple[str, ...]) -> str:
    """Create a directory path without following existing symlink components."""
    current = root
    for part in parts:
        current = os.path.join(current, part)
        try:
            current_stat = os.lstat(current)
        except FileNotFoundError:
            os.mkdir(current, 0o755)
            current_stat = os.lstat(current)

        if _is_unsafe_link(current, current_stat):
            raise UnsafeArchiveError(
                f"Archive output path contains a symlink: {current!r}"
            )
        if not stat.S_ISDIR(current_stat.st_mode):
            raise UnsafeArchiveError(
                f"Archive output parent is not a directory: {current!r}"
            )
    return current


def _validate_existing_paths(root: str, members: List[_ValidatedMember]) -> None:
    """Reject unsafe existing components before extracting the first file."""
    for member in members:
        current = root
        for index, part in enumerate(member.parts):
            current = os.path.join(current, part)
            if not os.path.lexists(current):
                # A missing parent means no deeper component can exist yet.
                break
            current_stat = os.lstat(current)
            if _is_unsafe_link(current, current_stat):
                raise UnsafeArchiveError(
                    f"Archive output path contains a symlink: {current!r}"
                )

            is_final = index == len(member.parts) - 1
            if not is_final or member.is_directory:
                if not stat.S_ISDIR(current_stat.st_mode):
                    raise UnsafeArchiveError(
                        f"Archive output parent is not a directory: {current!r}"
                    )
            elif not stat.S_ISREG(current_stat.st_mode):
                raise UnsafeArchiveError(
                    f"Archive output file conflicts with a non-file: {current!r}"
                )


def _replace_regular_file(
    root: str,
    parts: Tuple[str, ...],
    source: Any,
    mode: int,
) -> None:
    """Atomically replace one regular file without following its old inode."""
    parent = _ensure_directory(root, parts[:-1])
    target = os.path.join(parent, parts[-1])

    if os.path.lexists(target):
        target_stat = os.lstat(target)
        if _is_unsafe_link(target, target_stat):
            raise UnsafeArchiveError(
                f"Archive output file is an existing symlink: {target!r}"
            )
        if not stat.S_ISREG(target_stat.st_mode):
            raise UnsafeArchiveError(
                f"Archive output file conflicts with a non-file: {target!r}"
            )

    file_descriptor, temporary_path = tempfile.mkstemp(
        prefix=".dpdispatcher-extract-", dir=parent
    )
    try:
        with os.fdopen(file_descriptor, "wb") as output:
            shutil.copyfileobj(source, output)
        os.chmod(temporary_path, (mode & 0o777) or 0o600)

        # Recheck parents immediately before replacement.  os.replace replaces
        # a symlink at the final path rather than following it, while the fresh
        # temporary file avoids truncating a pre-existing hardlinked inode.
        _ensure_directory(root, parts[:-1])
        if os.path.lexists(target):
            target_stat = os.lstat(target)
            if _is_unsafe_link(target, target_stat):
                raise UnsafeArchiveError(
                    f"Archive output file became a symlink: {target!r}"
                )
        os.replace(temporary_path, target)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)


def _create_directories(root: str, members: List[_ValidatedMember]) -> None:
    """Create explicit and implicit member directories in parent-first order."""
    directories = {member.parts[:-1] for member in members if not member.is_directory}
    directories.update(member.parts for member in members if member.is_directory)
    for directory_parts in sorted(directories, key=lambda item: (len(item), item)):
        _ensure_directory(root, directory_parts)


def _apply_directory_modes(root: str, members: List[_ValidatedMember]) -> None:
    """Apply safe directory permissions after all child files are written."""
    for member in members:
        if member.is_directory and member.parts:
            directory = _ensure_directory(root, member.parts)
            os.chmod(directory, (member.mode & 0o777) or 0o755)


def safe_extract_tar(archive: tarfile.TarFile, destination: str) -> None:
    """Safely extract regular files and directories from a tar archive.

    The full manifest is validated before creating the output root.  Extraction
    rejects links, devices, traversal, path collisions, and existing symlink
    components.  Files are streamed to fresh temporary files and atomically
    replaced so existing hardlinks are not modified.

    The destination must not be concurrently renamed or mutated by another
    process during extraction; portable Python 3.7 has no cross-platform
    descriptor-relative API that can close that final local TOCTOU window.

    Parameters
    ----------
    archive : tarfile.TarFile
        Open tar archive containing remote result files.
    destination : str
        Directory under which every archive member must remain.

    Raises
    ------
    UnsafeArchiveError
        If the archive manifest or an existing output path is unsafe.
    """
    candidates = []
    for member in archive.getmembers():
        if not (member.isfile() or member.isdir()):
            raise UnsafeArchiveError(
                "Tar archive member is a link or special file: "
                f"{member.name!r} (type {member.type!r})"
            )
        candidates.append((member, member.name, member.isdir(), member.mode))

    members = _validate_manifest(candidates)
    root = _prepare_root(destination)
    _validate_existing_paths(root, members)
    _create_directories(root, members)
    for member in members:
        if member.is_directory:
            continue
        source = archive.extractfile(member.source)
        if source is None:
            raise UnsafeArchiveError(
                f"Tar regular file has no readable data: {member.source.name!r}"
            )
        with source:
            _replace_regular_file(root, member.parts, source, member.mode)
    _apply_directory_modes(root, members)


def safe_extract_zip(archive: zipfile.ZipFile, destination: str) -> None:
    """Safely extract regular files and directories from a zip archive.

    This applies the same manifest, symlink, and atomic-replacement guarantees
    as :func:`safe_extract_tar` while also validating Unix file types stored in
    zip metadata.

    Parameters
    ----------
    archive : zipfile.ZipFile
        Open zip archive containing remote result files.
    destination : str
        Directory under which every archive member must remain.

    Raises
    ------
    UnsafeArchiveError
        If the archive manifest or an existing output path is unsafe.
    """
    candidates = []
    for member in archive.infolist():
        mode = (member.external_attr >> 16) & 0xFFFF
        file_type = stat.S_IFMT(mode)
        expected_type = stat.S_IFDIR if member.is_dir() else stat.S_IFREG
        if file_type not in (0, expected_type):
            raise UnsafeArchiveError(
                "Zip archive member is a link or special file: "
                f"{member.filename!r} (mode {mode:o})"
            )
        candidates.append((member, member.filename, member.is_dir(), mode))

    members = _validate_manifest(candidates)
    root = _prepare_root(destination)
    _validate_existing_paths(root, members)
    _create_directories(root, members)
    for member in members:
        if member.is_directory:
            continue
        with archive.open(member.source, "r") as source:
            _replace_regular_file(root, member.parts, source, member.mode)
    _apply_directory_modes(root, members)
