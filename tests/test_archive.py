import io
import os
import stat
import subprocess
import tarfile
import tempfile
import unittest
import warnings
import zipfile

from dpdispatcher.utils.archive import (
    UnsafeArchiveError,
    safe_extract_tar,
    safe_extract_zip,
)


class SafeTarExtractionTest(unittest.TestCase):
    """Test validation of tar archives downloaded from remote backends."""

    @staticmethod
    def _add_file(archive: tarfile.TarFile, name: str, content: bytes) -> None:
        """Add an in-memory regular file to a test tar archive."""
        member = tarfile.TarInfo(name)
        member.mode = 0o644
        member.size = len(content)
        archive.addfile(member, io.BytesIO(content))

    def test_extracts_regular_files_and_directories(self) -> None:
        """A normal result archive is extracted without changing its layout."""
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, "valid.tar")
            output_dir = os.path.join(temp_dir, "output")
            with tarfile.open(archive_path, "w") as archive:
                directory = tarfile.TarInfo("task")
                directory.type = tarfile.DIRTYPE
                directory.mode = 0o755
                archive.addfile(directory)
                self._add_file(archive, "task/result.txt", b"result")

            with tarfile.open(archive_path, "r") as archive:
                safe_extract_tar(archive, output_dir)

            with open(os.path.join(output_dir, "task", "result.txt"), "rb") as fp:
                self.assertEqual(fp.read(), b"result")

    def test_rejects_traversal_and_absolute_paths_before_extracting(self) -> None:
        """Portable traversal and absolute path spellings are all rejected."""
        unsafe_names = (
            "../outside.txt",
            "nested/../../outside.txt",
            "..\\outside.txt",
            "/absolute.txt",
            "C:\\absolute.txt",
            "C:drive-relative.txt",
            "\\rooted.txt",
            "\\\\server\\share\\outside.txt",
            "result.txt:stream",
            "NUL.txt",
        )
        for unsafe_name in unsafe_names:
            with self.subTest(unsafe_name=unsafe_name):
                with tempfile.TemporaryDirectory() as temp_dir:
                    archive_path = os.path.join(temp_dir, "unsafe.tar")
                    output_dir = os.path.join(temp_dir, "output")
                    with tarfile.open(archive_path, "w") as archive:
                        # Complete validation must happen before this valid
                        # leading member can be written.
                        self._add_file(archive, "valid.txt", b"valid")
                        self._add_file(archive, unsafe_name, b"unsafe")

                    with tarfile.open(archive_path, "r") as archive:
                        with self.assertRaises(UnsafeArchiveError):
                            safe_extract_tar(archive, output_dir)

                    self.assertFalse(
                        os.path.exists(os.path.join(output_dir, "valid.txt"))
                    )

    def test_rejects_duplicate_and_prefix_conflicts(self) -> None:
        """Canonical aliases and file/directory conflicts are rejected."""
        unsafe_manifests = (
            (("result.txt", b"first"), ("./result.txt", b"second")),
            (("caf\u00e9.txt", b"first"), ("cafe\u0301.txt", b"second")),
            (("task", b"file"), ("task/result.txt", b"child")),
        )
        for manifest in unsafe_manifests:
            with self.subTest(manifest=manifest):
                with tempfile.TemporaryDirectory() as temp_dir:
                    archive_path = os.path.join(temp_dir, "unsafe.tar")
                    output_dir = os.path.join(temp_dir, "output")
                    with tarfile.open(archive_path, "w") as archive:
                        for name, content in manifest:
                            self._add_file(archive, name, content)

                    with tarfile.open(archive_path, "r") as archive:
                        with self.assertRaises(UnsafeArchiveError):
                            safe_extract_tar(archive, output_dir)

                    self.assertFalse(os.path.exists(output_dir))

    def test_rejects_existing_symlink_components(self) -> None:
        """Extraction never follows a symlink below the trusted output root."""
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, "result.tar")
            output_dir = os.path.join(temp_dir, "output")
            outside_dir = os.path.join(temp_dir, "outside")
            os.mkdir(output_dir)
            os.mkdir(outside_dir)
            try:
                os.symlink(outside_dir, os.path.join(output_dir, "task"))
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"symlinks are unavailable: {error}")

            with tarfile.open(archive_path, "w") as archive:
                self._add_file(archive, "valid.txt", b"valid")
                self._add_file(archive, "task/result.txt", b"result")

            with tarfile.open(archive_path, "r") as archive:
                with self.assertRaisesRegex(UnsafeArchiveError, "symlink"):
                    safe_extract_tar(archive, output_dir)

            self.assertFalse(os.path.exists(os.path.join(outside_dir, "result.txt")))
            self.assertFalse(os.path.exists(os.path.join(output_dir, "valid.txt")))

    def test_replaces_hardlinks_without_modifying_outside_inode(self) -> None:
        """Atomic replacement breaks an old hardlink before writing results."""
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, "result.tar")
            output_dir = os.path.join(temp_dir, "output")
            outside_file = os.path.join(temp_dir, "outside.txt")
            output_file = os.path.join(output_dir, "result.txt")
            os.mkdir(output_dir)
            with open(outside_file, "wb") as fp:
                fp.write(b"outside-original")
            try:
                os.link(outside_file, output_file)
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"hardlinks are unavailable: {error}")

            with tarfile.open(archive_path, "w") as archive:
                self._add_file(archive, "result.txt", b"archive-data")
            with tarfile.open(archive_path, "r") as archive:
                safe_extract_tar(archive, output_dir)

            with open(outside_file, "rb") as fp:
                self.assertEqual(fp.read(), b"outside-original")
            with open(output_file, "rb") as fp:
                self.assertEqual(fp.read(), b"archive-data")

    @unittest.skipUnless(os.name == "nt", "requires Windows directory junctions")
    def test_rejects_windows_directory_junctions(self) -> None:
        """Windows junction parents cannot redirect extraction outside."""
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, "result.tar")
            output_dir = os.path.join(temp_dir, "output")
            outside_dir = os.path.join(temp_dir, "outside")
            junction = os.path.join(output_dir, "task")
            os.mkdir(output_dir)
            os.mkdir(outside_dir)
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", junction, outside_dir],
                check=True,
                capture_output=True,
            )

            with tarfile.open(archive_path, "w") as archive:
                self._add_file(archive, "valid.txt", b"valid")
                self._add_file(archive, "task/result.txt", b"result")

            with tarfile.open(archive_path, "r") as archive:
                with self.assertRaisesRegex(UnsafeArchiveError, "symlink"):
                    safe_extract_tar(archive, output_dir)

            self.assertFalse(os.path.exists(os.path.join(outside_dir, "result.txt")))
            self.assertFalse(os.path.exists(os.path.join(output_dir, "valid.txt")))

    def test_rejects_links_and_special_files(self) -> None:
        """Tar links and device-like entries cannot affect the host filesystem."""
        unsafe_types = (
            tarfile.SYMTYPE,
            tarfile.LNKTYPE,
            tarfile.CHRTYPE,
            tarfile.BLKTYPE,
            tarfile.FIFOTYPE,
        )
        for unsafe_type in unsafe_types:
            with self.subTest(unsafe_type=unsafe_type):
                with tempfile.TemporaryDirectory() as temp_dir:
                    archive_path = os.path.join(temp_dir, "unsafe.tar")
                    with tarfile.open(archive_path, "w") as archive:
                        member = tarfile.TarInfo("unsafe")
                        member.type = unsafe_type
                        member.linkname = "../outside"
                        archive.addfile(member)

                    with tarfile.open(archive_path, "r") as archive:
                        with self.assertRaisesRegex(
                            UnsafeArchiveError, "link or special file"
                        ):
                            safe_extract_tar(archive, os.path.join(temp_dir, "output"))


class SafeZipExtractionTest(unittest.TestCase):
    """Test validation of zip archives downloaded from cloud backends."""

    def test_extracts_regular_files_and_directories(self) -> None:
        """A normal cloud result archive is extracted successfully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, "valid.zip")
            output_dir = os.path.join(temp_dir, "output")
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("task/", b"")
                archive.writestr("task/result.txt", b"result")

            with zipfile.ZipFile(archive_path, "r") as archive:
                safe_extract_zip(archive, output_dir)

            with open(os.path.join(output_dir, "task", "result.txt"), "rb") as fp:
                self.assertEqual(fp.read(), b"result")

    def test_rejects_traversal_and_absolute_paths_before_extracting(self) -> None:
        """Zip members cannot escape using POSIX or Windows path syntax."""
        unsafe_names = (
            "../outside.txt",
            "nested/../../outside.txt",
            "..\\outside.txt",
            "/absolute.txt",
            "C:\\absolute.txt",
            "C:drive-relative.txt",
            "\\rooted.txt",
            "\\\\server\\share\\outside.txt",
            "result.txt:stream",
            "NUL.txt",
        )
        for unsafe_name in unsafe_names:
            with self.subTest(unsafe_name=unsafe_name):
                with tempfile.TemporaryDirectory() as temp_dir:
                    archive_path = os.path.join(temp_dir, "unsafe.zip")
                    output_dir = os.path.join(temp_dir, "output")
                    with zipfile.ZipFile(archive_path, "w") as archive:
                        archive.writestr("valid.txt", b"valid")
                        archive.writestr(unsafe_name, b"unsafe")

                    with zipfile.ZipFile(archive_path, "r") as archive:
                        with self.assertRaises(UnsafeArchiveError):
                            safe_extract_zip(archive, output_dir)

                    self.assertFalse(
                        os.path.exists(os.path.join(output_dir, "valid.txt"))
                    )

    def test_rejects_duplicate_and_prefix_conflicts(self) -> None:
        """Canonical aliases and file/directory conflicts are rejected."""
        unsafe_manifests = (
            (("result.txt", b"first"), ("./result.txt", b"second")),
            (("caf\u00e9.txt", b"first"), ("cafe\u0301.txt", b"second")),
            (("task", b"file"), ("task/result.txt", b"child")),
        )
        for manifest in unsafe_manifests:
            with self.subTest(manifest=manifest):
                with tempfile.TemporaryDirectory() as temp_dir:
                    archive_path = os.path.join(temp_dir, "unsafe.zip")
                    output_dir = os.path.join(temp_dir, "output")
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", UserWarning)
                        with zipfile.ZipFile(archive_path, "w") as archive:
                            for name, content in manifest:
                                archive.writestr(name, content)

                    with zipfile.ZipFile(archive_path, "r") as archive:
                        with self.assertRaises(UnsafeArchiveError):
                            safe_extract_zip(archive, output_dir)

                    self.assertFalse(os.path.exists(output_dir))

    def test_rejects_existing_symlink_components(self) -> None:
        """Zip extraction never follows a symlink below the output root."""
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, "result.zip")
            output_dir = os.path.join(temp_dir, "output")
            outside_dir = os.path.join(temp_dir, "outside")
            os.mkdir(output_dir)
            os.mkdir(outside_dir)
            try:
                os.symlink(outside_dir, os.path.join(output_dir, "task"))
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"symlinks are unavailable: {error}")

            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("valid.txt", b"valid")
                archive.writestr("task/result.txt", b"result")

            with zipfile.ZipFile(archive_path, "r") as archive:
                with self.assertRaisesRegex(UnsafeArchiveError, "symlink"):
                    safe_extract_zip(archive, output_dir)

            self.assertFalse(os.path.exists(os.path.join(outside_dir, "result.txt")))
            self.assertFalse(os.path.exists(os.path.join(output_dir, "valid.txt")))

    def test_replaces_hardlinks_without_modifying_outside_inode(self) -> None:
        """Zip extraction atomically replaces rather than truncates hardlinks."""
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, "result.zip")
            output_dir = os.path.join(temp_dir, "output")
            outside_file = os.path.join(temp_dir, "outside.txt")
            output_file = os.path.join(output_dir, "result.txt")
            os.mkdir(output_dir)
            with open(outside_file, "wb") as fp:
                fp.write(b"outside-original")
            try:
                os.link(outside_file, output_file)
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"hardlinks are unavailable: {error}")

            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("result.txt", b"archive-data")
            with zipfile.ZipFile(archive_path, "r") as archive:
                safe_extract_zip(archive, output_dir)

            with open(outside_file, "rb") as fp:
                self.assertEqual(fp.read(), b"outside-original")
            with open(output_file, "rb") as fp:
                self.assertEqual(fp.read(), b"archive-data")

    def test_rejects_unix_links_and_special_files(self) -> None:
        """Unix mode metadata cannot request symlink or device extraction."""
        unsafe_modes = (
            stat.S_IFLNK | 0o777,
            stat.S_IFCHR | 0o600,
            stat.S_IFBLK | 0o600,
            stat.S_IFIFO | 0o600,
        )
        for unsafe_mode in unsafe_modes:
            with self.subTest(unsafe_mode=unsafe_mode):
                with tempfile.TemporaryDirectory() as temp_dir:
                    archive_path = os.path.join(temp_dir, "unsafe.zip")
                    with zipfile.ZipFile(archive_path, "w") as archive:
                        member = zipfile.ZipInfo("unsafe")
                        member.create_system = 3
                        member.external_attr = unsafe_mode << 16
                        archive.writestr(member, b"../outside")

                    with zipfile.ZipFile(archive_path, "r") as archive:
                        with self.assertRaisesRegex(
                            UnsafeArchiveError, "link or special file"
                        ):
                            safe_extract_zip(archive, os.path.join(temp_dir, "output"))


if __name__ == "__main__":
    unittest.main()
