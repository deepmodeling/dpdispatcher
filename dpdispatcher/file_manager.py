"""Object-oriented file staging primitives used by execution contexts.

The public ``Task`` and ``Submission`` APIs intentionally still expose file
names as strings.  This module turns those strings into validated, deterministic
manifests before a context performs any I/O.  Keeping path policy and transfer
bookkeeping here prevents each backend from subtly interpreting globs,
directories, and missing files differently.
"""

from __future__ import annotations

import fnmatch
import glob as glob_module
import ntpath
import os
import shutil
import stat
import tarfile
import uuid
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dpdispatcher.submission import Submission, Task

_GLOB_CHARS = "*?["


class PathPolicy:
    """Validate and resolve paths relative to a staging root.

    User-provided task paths are intentionally lexical paths rather than
    arbitrary filesystem paths.  Rejecting absolute paths and ``..`` segments
    here prevents ``os.path.join(root, value)`` from escaping the submission
    directory on local, SSH, and archive-backed contexts.
    """

    @staticmethod
    def normalize_relative(
        value: os.PathLike[str] | str, *, allow_glob: bool = False
    ) -> str:
        """Return a canonical, safe path relative to a staging root."""
        if isinstance(value, os.PathLike):
            value = os.fspath(value)
        if not isinstance(value, str):
            raise TypeError(f"path must be a string, got {type(value).__name__}")
        if "\x00" in value:
            raise ValueError("path must not contain a NUL byte")

        # DPDispatcher's remote paths are POSIX paths even when a local caller
        # happens to use a platform-specific separator.
        value = value.replace("\\", "/")
        # ``ntpath`` catches drive-qualified Windows paths even when a task is
        # validated on a POSIX controller (where ``os.path.isabs('C:/...')``
        # would otherwise be false).
        if value.startswith("/") or ntpath.splitdrive(value)[0]:
            raise ValueError(
                f"absolute paths are not allowed in staging entries: {value}"
            )

        parts = value.split("/")
        if any(part == ".." for part in parts):
            raise ValueError(f"parent-directory traversal is not allowed: {value}")
        if not allow_glob and any(char in value for char in _GLOB_CHARS):
            raise ValueError(f"glob patterns are not allowed here: {value}")

        # Empty components and '.' are harmless, but canonicalising them makes
        # manifest comparison and duplicate detection deterministic.
        canonical = "/".join(part for part in parts if part not in ("", "."))
        return canonical or "."

    @classmethod
    def join_relative(cls, prefix: str, suffix: str) -> str:
        """Join two validated relative paths without introducing traversal."""
        prefix = cls.normalize_relative(prefix, allow_glob=False)
        # ``suffix`` is often a concrete filename returned by glob expansion;
        # wildcard characters are then literal data rather than a new pattern.
        suffix = cls.normalize_relative(suffix, allow_glob=True)
        if prefix == ".":
            return suffix
        if suffix == ".":
            return prefix
        return cls.normalize_relative(f"{prefix}/{suffix}", allow_glob=True)


class PathResolver:
    """Resolve validated relative paths and glob patterns under one root."""

    def __init__(self, root: os.PathLike[str] | str) -> None:
        # ``Path.absolute`` preserves ``..``; collapse it once so containment
        # checks cannot be bypassed by parent-directory components.
        self.root = Path(os.path.normpath(os.fspath(Path(root).absolute())))

    def resolve(
        self,
        value: os.PathLike[str] | str,
        *,
        allow_glob: bool = False,
        allow_absolute: bool = False,
    ) -> Path:
        """Resolve a relative path, optionally allowing an in-root absolute path."""
        if os.path.isabs(value):
            if not allow_absolute:
                raise ValueError(
                    f"absolute paths are not allowed in staging entries: {value}"
                )
            candidate = Path(os.path.normpath(os.fspath(Path(value).absolute())))
            try:
                candidate.relative_to(self.root)
            except ValueError as error:
                raise ValueError(
                    f"path {candidate} is outside staging root {self.root}"
                ) from error
            return candidate
        relative = PathPolicy.normalize_relative(value, allow_glob=allow_glob)
        return self.root / Path(relative)

    def relative(self, value: os.PathLike[str] | str) -> str:
        """Return the canonical path of ``value`` relative to this root."""
        candidate = Path(os.path.normpath(os.fspath(Path(value).absolute())))
        try:
            relative = candidate.relative_to(self.root)
        except ValueError as error:
            raise ValueError(
                f"path {candidate} is outside staging root {self.root}"
            ) from error
        # Concrete matches may legitimately contain ``*``, ``?`` or ``[``.
        return PathPolicy.normalize_relative(relative.as_posix(), allow_glob=True)

    def expand(self, pattern: os.PathLike[str] | str) -> list[Path]:
        """Expand one path or glob deterministically.

        ``glob`` does not report broken symlinks for a literal path, so literal
        entries use ``lexists`` and produce a clear error for a broken link.
        """
        normalized = PathPolicy.normalize_relative(pattern, allow_glob=True)
        candidate = self.root / Path(normalized)
        if any(char in normalized for char in _GLOB_CHARS):
            # Escape only the staging root.  The user pattern remains active
            # so its wildcard operators retain their intended meaning.
            pattern = os.path.join(
                glob_module.escape(os.fspath(self.root)),
                *normalized.split("/"),
            )
            matches = glob_module.glob(pattern, recursive=True)
            return [Path(match) for match in sorted(matches)]
        if os.path.lexists(candidate):
            return [candidate]
        return []


@dataclass(frozen=True)
class FileEntry:
    """One concrete source-to-destination transfer in a manifest."""

    source: Path
    destination: str

    @property
    def is_symlink(self) -> bool:
        """Whether the source entry is a symbolic link."""
        return self.source.is_symlink()

    @property
    def is_directory(self) -> bool:
        """Whether the source entry is a real directory rather than a link."""
        return self.source.is_dir() and not self.source.is_symlink()


@dataclass(frozen=True)
class MissingEntry:
    """A requested path that was absent from the source and fallback roots."""

    pattern: str
    destination_prefix: str

    def failure_marker(self) -> str:
        """Return a safe, deterministic marker filename for this request."""
        safe_pattern = "".join(
            char if (char.isalnum() or char in ".-_") else "_"
            for char in str(self.pattern)
        )
        return PathPolicy.join_relative(
            self.destination_prefix, f"tag_failure_download_{safe_pattern}"
        )


@dataclass
class ResolvedManifest:
    """Concrete transfers plus requests that could not be resolved."""

    entries: list[FileEntry]
    missing: list[MissingEntry]

    def unique(self) -> ResolvedManifest:
        """Return a deterministic manifest with duplicate paths removed."""
        by_destination = {}
        for entry in self.entries:
            old = by_destination.get(entry.destination)
            if old is not None and old.source != entry.source:
                raise ValueError(
                    "multiple source files map to the same destination "
                    f"{entry.destination}: {old.source} and {entry.source}"
                )
            by_destination[entry.destination] = entry
        return ResolvedManifest(
            entries=[by_destination[key] for key in sorted(by_destination)],
            missing=list(self.missing),
        )


class ManifestBuilder:
    """Build upload/download manifests from task and common-file selections."""

    def __init__(self) -> None:
        self._entries: list[FileEntry] = []
        self._missing: list[MissingEntry] = []

    def add_paths(
        self,
        *,
        source_root: os.PathLike[str] | str,
        destination_prefix: str,
        patterns: Sequence[str],
        required: bool = True,
        fallback_root: os.PathLike[str] | str | None = None,
    ) -> ManifestBuilder:
        """Expand patterns below a source root and append transfer entries."""
        resolver = PathResolver(source_root)
        fallback = PathResolver(fallback_root) if fallback_root is not None else None
        destination_prefix = PathPolicy.normalize_relative(
            destination_prefix, allow_glob=False
        )

        for pattern in patterns:
            normalized_pattern = PathPolicy.normalize_relative(pattern, allow_glob=True)
            matches = resolver.expand(normalized_pattern)
            if not matches:
                # A local file already present from an earlier download is a
                # valid idempotent fallback.  It is deliberately not added to
                # the transfer list because there is no source to copy.
                if fallback is not None and fallback.expand(normalized_pattern):
                    continue
                if required:
                    self._missing.append(
                        MissingEntry(normalized_pattern, destination_prefix)
                    )
                continue

            for match in matches:
                relative = resolver.relative(match)
                destination = PathPolicy.join_relative(destination_prefix, relative)
                self._entries.append(FileEntry(source=match, destination=destination))
        return self

    def add_directory(self, destination: str) -> ManifestBuilder:
        """Add an empty directory marker to preserve task directories."""
        destination = PathPolicy.normalize_relative(destination, allow_glob=False)
        self._entries.append(FileEntry(source=Path("."), destination=destination))
        return self

    def build(self) -> ResolvedManifest:
        """Return a deduplicated immutable snapshot of the collected entries."""
        # ``Path('.')`` is a marker only; callers that need to create an empty
        # directory handle it separately from regular source entries.
        return ResolvedManifest(self._entries, self._missing).unique()

    @property
    def missing(self) -> list[MissingEntry]:
        """Return unresolved required requests accumulated so far."""
        return list(self._missing)


class RemoteManifestBuilder:
    """Build a manifest from an indexed, non-filesystem source.

    SSH and similar transports cannot pass a remote path to :mod:`glob` on the
    client machine.  They first index regular files below the remote root and
    then use this builder to apply the same destination and missing-entry
    policy as :class:`ManifestBuilder`.  Literal paths may optionally be
    checked through ``exists``; leaving that callback unset preserves the
    historical behavior where the remote tar command reports a missing
    literal file when ``check_exists`` is disabled.
    """

    def __init__(
        self,
        available_paths: Sequence[str] = (),
        *,
        exists: Callable[[str], bool] | None = None,
        assume_literals: bool = True,
    ) -> None:
        self._available = {
            # Indexed paths are concrete names, so glob characters must be
            # retained literally instead of being rejected as patterns.
            PathPolicy.normalize_relative(path, allow_glob=True)
            for path in available_paths
        }
        self._exists = exists
        self._assume_literals = assume_literals
        self._entries: list[FileEntry] = []
        self._missing: list[MissingEntry] = []

    def add_paths(
        self,
        *,
        source_prefix: str,
        destination_prefix: str,
        patterns: Sequence[str],
        required: bool = True,
    ) -> RemoteManifestBuilder:
        """Match remote patterns against the indexed path set."""
        source_prefix = PathPolicy.normalize_relative(source_prefix, allow_glob=False)
        destination_prefix = PathPolicy.normalize_relative(
            destination_prefix, allow_glob=False
        )
        for pattern in patterns:
            normalized = PathPolicy.normalize_relative(pattern, allow_glob=True)
            if any(char in normalized for char in _GLOB_CHARS):
                matches = []
                for available in self._available:
                    relative = self._relative_to_prefix(available, source_prefix)
                    if relative is not None and self._match_path(relative, normalized):
                        matches.append((relative, available))
            else:
                relative = normalized
                candidate = PathPolicy.join_relative(source_prefix, relative)
                if candidate in self._available:
                    matches = [(relative, candidate)]
                elif self._exists is not None and self._exists(candidate):
                    matches = [(relative, candidate)]
                elif self._assume_literals:
                    matches = [(relative, candidate)]
                else:
                    matches = []

            if not matches:
                if required:
                    self._missing.append(MissingEntry(normalized, destination_prefix))
                continue
            for relative, source in sorted(matches):
                self._entries.append(
                    FileEntry(
                        source=Path(source),
                        destination=PathPolicy.join_relative(
                            destination_prefix, relative
                        ),
                    )
                )
        return self

    @staticmethod
    def _match_path(path: str, pattern: str) -> bool:
        """Match slash-separated paths without letting ``*`` cross ``/``.

        Ordinary wildcards match one segment, while ``**`` recursively matches
        zero or more segments, mirroring local :mod:`glob` semantics.
        """
        path_parts = tuple(part for part in path.split("/") if part not in ("", "."))
        pattern_parts = tuple(
            part for part in pattern.split("/") if part not in ("", ".")
        )

        @cache
        def match(path_index: int, pattern_index: int) -> bool:
            if pattern_index == len(pattern_parts):
                return path_index == len(path_parts)
            token = pattern_parts[pattern_index]
            if token == "**":
                return match(path_index, pattern_index + 1) or (
                    path_index < len(path_parts)
                    and not path_parts[path_index].startswith(".")
                    and match(path_index + 1, pattern_index)
                )
            return (
                path_index < len(path_parts)
                and (
                    pattern_parts[pattern_index].startswith(".")
                    or not path_parts[path_index].startswith(".")
                )
                and fnmatch.fnmatchcase(path_parts[path_index], token)
                and match(path_index + 1, pattern_index + 1)
            )

        return match(0, 0)

    @staticmethod
    def _relative_to_prefix(path: str, prefix: str) -> str | None:
        if prefix == ".":
            return path
        if path == prefix:
            return "."
        marker = prefix + "/"
        if path.startswith(marker):
            return path[len(marker) :]
        return None

    def build(self) -> ResolvedManifest:
        """Return a deduplicated manifest for the indexed remote paths."""
        return ResolvedManifest(self._entries, self._missing).unique()


class SubmissionStagingPlan:
    """Compile a ``Submission`` into upload and download manifests.

    The plan is deliberately independent from a transport implementation.  A
    local copier, SFTP archive transport, and HDFS adapter can therefore apply
    the same path semantics without each backend walking tasks again.
    """

    def __init__(
        self, local_root: os.PathLike[str] | str, submission: Submission
    ) -> None:
        self.local_root = PathResolver(local_root).root
        self.submission = submission

    @staticmethod
    def _task_path(task: Task) -> str:
        return PathPolicy.normalize_relative(task.task_work_path, allow_glob=False)

    def upload_manifest(
        self, *, include_tasks: bool = True, include_common: bool = True
    ) -> ResolvedManifest:
        """Resolve all required forward files from the local work root."""
        builder = ManifestBuilder()
        local = PathResolver(self.local_root)
        if include_tasks:
            for task in self.submission.belonging_tasks:
                task_path = self._task_path(task)
                builder.add_directory(task_path)
                builder.add_paths(
                    source_root=local.resolve(task_path),
                    destination_prefix=task_path,
                    patterns=task.forward_files,
                    required=True,
                )
        if include_common:
            builder.add_paths(
                source_root=self.local_root,
                destination_prefix=".",
                patterns=self.submission.forward_common_files,
                required=True,
            )
        return builder.build()

    def download_manifest(
        self,
        remote_root: os.PathLike[str] | str,
        *,
        fallback_root: os.PathLike[str] | str | None = None,
        include_errors: bool = False,
    ) -> ResolvedManifest:
        """Resolve backward files from a remote root.

        ``fallback_root`` makes a download idempotent: if a previous attempt
        already copied a requested file locally, its absence on the remote side
        is not reported as a new missing artifact.
        """
        builder = ManifestBuilder()
        remote = PathResolver(remote_root)
        fallback = PathResolver(fallback_root) if fallback_root is not None else None
        for task in self.submission.belonging_tasks:
            task_path = self._task_path(task)
            remote_task = remote.resolve(task_path)
            fallback_task = (
                fallback.resolve(task_path) if fallback is not None else None
            )
            builder.add_paths(
                source_root=remote_task,
                destination_prefix=task_path,
                patterns=task.backward_files,
                required=True,
                fallback_root=fallback_task,
            )
            if include_errors:
                builder.add_paths(
                    source_root=remote_task,
                    destination_prefix=task_path,
                    patterns=["error*"],
                    required=False,
                )

        builder.add_paths(
            source_root=remote_root,
            destination_prefix=".",
            patterns=self.submission.backward_common_files,
            required=True,
            fallback_root=fallback_root,
        )
        if include_errors:
            builder.add_paths(
                source_root=remote_root,
                destination_prefix=".",
                patterns=["error*"],
                required=False,
            )
        return builder.build()


class ArchiveBuilder:
    """Build deterministic zip archives from a validated file selection."""

    def __init__(self, root: os.PathLike[str] | str) -> None:
        self.root = PathResolver(root)

    def build_zip(
        self,
        archive_path: os.PathLike[str] | str,
        patterns: Sequence[str],
    ) -> Path:
        """Create a zip archive containing selected files and directories."""
        manifest = (
            ManifestBuilder()
            .add_paths(
                source_root=self.root.root,
                destination_prefix=".",
                patterns=patterns,
                required=True,
            )
            .build()
        )
        if manifest.missing:
            missing = manifest.missing[0]
            raise FileNotFoundError(
                f"cannot find archive input {missing.pattern} under {self.root.root}"
            )

        output = Path(archive_path)
        if not output.is_absolute():
            output = self.root.root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        written = set()
        with zipfile.ZipFile(output, mode="w") as archive:
            for entry in manifest.entries:
                if entry.destination in written:
                    continue
                written.add(entry.destination)
                if entry.is_directory:
                    archive.write(entry.source, entry.destination)
                    for child in sorted(entry.source.rglob("*")):
                        relative = child.relative_to(entry.source).as_posix()
                        child_destination = PathPolicy.join_relative(
                            entry.destination, relative
                        )
                        if child_destination in written:
                            continue
                        written.add(child_destination)
                        archive.write(child, child_destination)
                else:
                    archive.write(entry.source, entry.destination)
        return output


class FileTransfer:
    """Apply a concrete manifest between filesystem-backed roots."""

    def __init__(
        self,
        destination_root: os.PathLike[str] | str,
        *,
        symlink: bool = False,
        link_sources: bool = False,
        move: bool = False,
        overwrite: bool = True,
    ) -> None:
        self.destination = PathResolver(destination_root)
        self.symlink = symlink
        self.link_sources = link_sources
        self.move = move
        self.overwrite = overwrite

    @staticmethod
    def remove(path: os.PathLike[str] | str) -> None:
        """Remove a file, directory, or broken symlink without following it."""
        if not os.path.lexists(path):
            return
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

    def apply(self, manifest: ResolvedManifest) -> None:
        """Apply all manifest entries, respecting move/link/overwrite policy."""
        moved_directories = []
        for entry in manifest.entries:
            if entry.source == Path("."):
                self.destination.resolve(entry.destination).mkdir(
                    parents=True, exist_ok=True
                )
                continue
            target = self.destination.resolve(entry.destination)
            # Moving a directory already moves every selected child beneath
            # it.  Skip overlapping child entries so a manifest produced from
            # patterns such as ``["task", "task/*"]`` remains valid after the
            # parent directory has been moved.
            if self.move and any(
                self._is_descendant(entry.source, source_dir)
                and self._is_descendant(target, target_dir)
                for source_dir, target_dir in moved_directories
            ):
                continue
            source_is_directory = (
                entry.source.is_dir() and not entry.source.is_symlink()
            )
            # LocalContext can be configured with overlapping local and remote
            # roots.  Never remove a source when the two paths resolve to the
            # same file during an idempotent download.
            if os.path.realpath(entry.source) == os.path.realpath(target):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if self.overwrite:
                self._copy_one(entry.source, target)
            else:
                self._copy_missing_one(entry.source, target)
            if self.move and source_is_directory:
                moved_directories.append((entry.source, target))

    @staticmethod
    def _is_descendant(path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
        except ValueError:
            return False
        return path != parent

    def _copy_one(self, source: Path, target: Path) -> None:
        self.remove(target)
        if self.move and not source.is_symlink():
            shutil.move(os.fspath(source), os.fspath(target))
            return
        if self.link_sources:
            os.symlink(os.fspath(source), target)
        elif source.is_symlink() and self.symlink:
            os.symlink(os.readlink(source), target)
        elif source.is_dir():
            shutil.copytree(source, target, symlinks=self.symlink)
        else:
            # copy2 follows links when symlink preservation is disabled, which
            # is the desired download behavior for generated symlink artifacts.
            shutil.copy2(source, target, follow_symlinks=not self.symlink)

    def _copy_missing_one(self, source: Path, target: Path) -> None:
        """Copy only paths absent at the destination, preserving existing data."""
        if os.path.lexists(target):
            if source.is_dir() and target.is_dir() and not target.is_symlink():
                for child in source.iterdir():
                    self._copy_missing_one(child, target / child.name)
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        if self.link_sources:
            try:
                os.symlink(os.fspath(source), target)
            except FileExistsError:
                pass
        elif source.is_dir():
            shutil.copytree(source, target, symlinks=self.symlink)
        else:
            shutil.copy2(source, target, follow_symlinks=not self.symlink)


class AtomicTextWriter:
    """Atomically write UTF-8 text below a validated root."""

    def __init__(self, root: os.PathLike[str] | str) -> None:
        self.root = PathResolver(root)

    def write(self, relative_path: str, content: str) -> Path:
        """Atomically write UTF-8 content below the configured root."""
        target = self.root.resolve(relative_path, allow_absolute=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.parent / f".{target.name}.{uuid.uuid4().hex}.tmp"
        try:
            with open(temporary, "w", encoding="utf-8") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.lexists(temporary):
                os.remove(temporary)
        return target


class SafeArchiveExtractor:
    """Extract tar/zip archives without allowing paths outside a destination."""

    def __init__(self, destination: os.PathLike[str] | str) -> None:
        self.destination = Path(destination).absolute()
        self.destination.mkdir(parents=True, exist_ok=True)

    def _member_path(self, name: str) -> Path:
        if "\x00" in name:
            raise ValueError("archive member contains a NUL byte")
        # Archive member names are literal filenames; wildcard characters are
        # valid data here and must not be interpreted as selection patterns.
        relative = PathPolicy.normalize_relative(name, allow_glob=True)
        candidate = (self.destination / relative).absolute()
        try:
            candidate.relative_to(self.destination)
        except ValueError as error:
            raise ValueError(
                f"archive member escapes extraction root: {name}"
            ) from error
        # Lexical containment is not enough when the destination already
        # contains a symlink (for example ``out/data -> /tmp``).  Reject links
        # in every existing component, including the final output path, before
        # opening or creating anything so an archive cannot redirect writes.
        current = self.destination
        components = candidate.relative_to(self.destination).parts
        for component in components:
            current /= component
            if current.is_symlink():
                raise ValueError(
                    f"archive member traverses a symlink in extraction root: {name}"
                )
        return candidate

    def extract_tar(self, archive: os.PathLike[str] | str) -> set[str]:
        """Safely extract a tar archive and return extracted file names."""
        with tarfile.open(archive, mode="r:*") as tar:
            members = tar.getmembers()
            for member in members:
                target = self._member_path(member.name)
                if member.issym() or member.islnk():
                    # A link can redirect a later archive member outside the
                    # extraction root.  Current DPDispatcher download archives
                    # dereference links, so rejecting them is the safe default.
                    raise ValueError(f"archive links are not allowed: {member.name}")
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
            for member in members:
                if member.isdir():
                    continue
                target = self._member_path(member.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                extracted = tar.extractfile(member)
                if extracted is None:
                    raise ValueError(f"unsupported tar member: {member.name}")
                with open(target, "wb") as output:
                    shutil.copyfileobj(extracted, output)
        return {Path(member.name).as_posix() for member in members if member.isfile()}

    def extract_zip(self, archive: os.PathLike[str] | str) -> set[str]:
        """Safely extract a zip archive and return extracted file names."""
        with zipfile.ZipFile(archive, mode="r") as zipped:
            extracted_files: set[str] = set()
            for member in zipped.infolist():
                target = self._member_path(member.filename)
                mode = (member.external_attr >> 16) & 0o170000
                if stat.S_ISLNK(mode):
                    raise ValueError(
                        f"archive links are not allowed: {member.filename}"
                    )
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with (
                    zipped.open(member, mode="r") as source,
                    open(target, "wb") as output,
                ):
                    shutil.copyfileobj(source, output)
                extracted_files.add(Path(member.filename).as_posix())
        return extracted_files


def write_text_atomic(
    root: os.PathLike[str] | str, relative_path: str, content: str
) -> Path:
    """Compatibility helper for contexts that only need one atomic write."""
    return AtomicTextWriter(root).write(relative_path, content)
