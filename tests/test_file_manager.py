"""Unit tests for the object-oriented staging primitives."""

import io
import os
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from dpdispatcher.file_manager import (
    ArchiveBuilder,
    AtomicTextWriter,
    FileEntry,
    FileTransfer,
    ManifestBuilder,
    PathPolicy,
    PathResolver,
    RemoteManifestBuilder,
    ResolvedManifest,
    SafeArchiveExtractor,
)


class TestPathPolicy(unittest.TestCase):
    def test_normalizes_safe_relative_paths(self) -> None:
        self.assertEqual(PathPolicy.normalize_relative("./task//input"), "task/input")
        self.assertEqual(PathPolicy.normalize_relative("."), ".")
        self.assertEqual(
            PathPolicy.normalize_relative(Path("task/input")), "task/input"
        )

    def test_rejects_paths_that_escape_root(self) -> None:
        with self.assertRaises(ValueError):
            PathPolicy.normalize_relative("../outside")
        with self.assertRaises(ValueError):
            PathPolicy.normalize_relative("/absolute")
        with self.assertRaises(ValueError):
            PathPolicy.normalize_relative("C:/absolute")
        with self.assertRaises(ValueError):
            PathPolicy.normalize_relative("a\x00b")

    def test_absolute_paths_are_normalized_before_containment_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "root"
            root.mkdir()
            resolver = PathResolver(root)
            with self.assertRaises(ValueError):
                resolver.resolve(root / ".." / "outside", allow_absolute=True)

    def test_glob_expansion_escapes_metacharacters_in_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "root[1]"
            root.mkdir()
            (root / "result.txt").write_text("result", encoding="utf-8")

            self.assertEqual(PathResolver(root).expand("*.txt"), [root / "result.txt"])


class TestManifestAndTransfer(unittest.TestCase):
    def test_manifest_expands_globs_and_preserves_empty_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "source"
            destination = Path(temp_dir) / "destination"
            (root / "task").mkdir(parents=True)
            (root / "task" / "a.txt").write_text("a", encoding="utf-8")

            builder = ManifestBuilder()
            builder.add_directory("task")
            builder.add_paths(
                source_root=root / "task",
                destination_prefix="task",
                patterns=["*.txt"],
            )
            manifest = builder.build()
            FileTransfer(destination).apply(manifest)

            self.assertEqual(
                (destination / "task" / "a.txt").read_text(encoding="utf-8"), "a"
            )
            self.assertTrue((destination / "task").is_dir())

    @unittest.skipUnless(os.name == "posix", "symlinks are not available")
    def test_link_sources_matches_local_context_symlink_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "source"
            destination = Path(temp_dir) / "destination"
            root.mkdir()
            source = root / "input.txt"
            source.write_text("input", encoding="utf-8")
            manifest = (
                ManifestBuilder()
                .add_paths(
                    source_root=root, destination_prefix=".", patterns=["input.txt"]
                )
                .build()
            )

            FileTransfer(destination, link_sources=True).apply(manifest)

            target = destination / "input.txt"
            self.assertTrue(target.is_symlink())
            self.assertEqual(target.resolve(), source.resolve())

    def test_move_skips_children_already_moved_with_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "source"
            destination = Path(temp_dir) / "destination"
            (root / "task").mkdir(parents=True)
            (root / "task" / "result.txt").write_text("result", encoding="utf-8")
            manifest = ResolvedManifest(
                entries=[
                    FileEntry(root / "task", "task"),
                    FileEntry(root / "task" / "result.txt", "task/result.txt"),
                ],
                missing=[],
            )

            FileTransfer(destination, move=True).apply(manifest)

            self.assertEqual(
                (destination / "task" / "result.txt").read_text(encoding="utf-8"),
                "result",
            )

    def test_missing_entries_and_duplicate_destinations_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "a").write_text("a", encoding="utf-8")
            builder = ManifestBuilder()
            builder.add_paths(
                source_root=root,
                destination_prefix=".",
                patterns=["missing"],
            )
            self.assertEqual(builder.build().missing[0].pattern, "missing")
            with self.assertRaises(ValueError):
                ResolvedManifest(
                    entries=[
                        FileEntry(root / "a", "out.txt"),
                        FileEntry(root / "b", "out.txt"),
                    ],
                    missing=[],
                ).unique()

    def test_literal_glob_characters_survive_manifest_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            literal = root / "data[1].out"
            literal.write_text("result", encoding="utf-8")

            manifest = (
                ManifestBuilder()
                .add_paths(source_root=root, destination_prefix=".", patterns=["*"])
                .build()
            )

            self.assertEqual(
                [entry.destination for entry in manifest.entries], ["data[1].out"]
            )

    def test_remote_manifest_uses_indexed_paths_for_globs(self) -> None:
        manifest = (
            RemoteManifestBuilder(["task/a.out", "task/nested/b.out", "common.out"])
            .add_paths(
                source_prefix="task",
                destination_prefix="task",
                patterns=["*.out"],
            )
            .add_paths(
                source_prefix=".",
                destination_prefix=".",
                patterns=["common.out"],
            )
            .build()
        )
        self.assertEqual(
            [entry.destination for entry in manifest.entries],
            ["common.out", "task/a.out"],
        )

        nested = (
            RemoteManifestBuilder(["task/a.out", "task/nested/b.out"])
            .add_paths(
                source_prefix="task",
                destination_prefix="task",
                patterns=["nested/*.out"],
            )
            .build()
        )
        self.assertEqual(
            [entry.destination for entry in nested.entries], ["task/nested/b.out"]
        )

        recursive = (
            RemoteManifestBuilder(["task/a.out", "task/nested/b.out"])
            .add_paths(
                source_prefix="task",
                destination_prefix="task",
                patterns=["**/*.out"],
            )
            .build()
        )
        self.assertEqual(
            [entry.destination for entry in recursive.entries],
            ["task/a.out", "task/nested/b.out"],
        )

        hidden = (
            RemoteManifestBuilder(["task/.hidden.out", "task/visible.out"])
            .add_paths(
                source_prefix="task",
                destination_prefix="task",
                patterns=["*.out"],
            )
            .build()
        )
        self.assertEqual(
            [entry.destination for entry in hidden.entries], ["task/visible.out"]
        )


class TestAtomicFilesAndArchives(unittest.TestCase):
    def test_archive_builder_deduplicates_and_recurses_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "source"
            root.mkdir()
            (root / "inputs").mkdir()
            (root / "inputs" / "config.txt").write_text("config", encoding="utf-8")
            archive_path = ArchiveBuilder(root).build_zip(
                Path(temp_dir) / "inputs.zip", ["inputs", "inputs/config.txt"]
            )
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(archive.namelist(), ["inputs/", "inputs/config.txt"])

    def test_atomic_writer_creates_parent_and_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            writer = AtomicTextWriter(temp_dir)
            writer.write("meta/state.json", "{}")
            self.assertEqual(
                (Path(temp_dir) / "meta" / "state.json").read_text(encoding="utf-8"),
                "{}",
            )
            with self.assertRaises(ValueError):
                writer.write("../escape", "bad")

    def test_tar_and_zip_extractors_reject_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            tar_path = temp / "bad.tar"
            with tarfile.open(tar_path, "w") as archive:
                payload = tarfile.TarInfo("../escape.txt")
                payload.size = 4
                archive.addfile(payload, io.BytesIO(b"oops"))
            with self.assertRaises(ValueError):
                SafeArchiveExtractor(temp / "tar-out").extract_tar(tar_path)
            self.assertFalse((temp / "escape.txt").exists())

            zip_path = temp / "bad.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("../escape.txt", "oops")
            with self.assertRaises(ValueError):
                SafeArchiveExtractor(temp / "zip-out").extract_zip(zip_path)
            self.assertFalse((temp / "escape.txt").exists())

    @unittest.skipUnless(os.name == "posix", "symlinks are not available")
    def test_extractors_reject_preexisting_symlink_components(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            outside = temp / "outside"
            outside.mkdir()
            zip_path = temp / "link.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("data/result.txt", "must not escape")

            output = temp / "zip-out"
            output.mkdir()
            (output / "data").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                SafeArchiveExtractor(output).extract_zip(zip_path)
            self.assertFalse((outside / "result.txt").exists())
