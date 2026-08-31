"""Stage DistributedShell submission data through HDFS archives."""

import os
import shutil
import tarfile
import tempfile
from glob import glob
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn

from dpdispatcher.base_context import BaseContext
from dpdispatcher.dlog import dlog
from dpdispatcher.file_manager import (
    AtomicTextWriter,
    FileTransfer,
    PathPolicy,
    PathResolver,
    SafeArchiveExtractor,
    SubmissionStagingPlan,
)
from dpdispatcher.utils.hdfs_cli import HDFS, HDFSMissingPathError

if TYPE_CHECKING:
    from dpdispatcher.submission import Submission


class HDFSContext(BaseContext):
    """Transfer submission inputs and outputs between local storage and HDFS."""

    # DistributedShell emits one archive per grouped job, and only emits it
    # after every task succeeds.  Submission.download_jobs must therefore
    # select complete jobs instead of attempting partial archive downloads.
    downloads_by_job = True
    supports_partial_job_download = False

    def __init__(
        self,
        local_root: str,
        remote_root: str,
        remote_profile: dict[str, Any] | None = None,  # noqa: ANN401
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        assert isinstance(local_root, str)
        self.init_local_root = local_root
        self.init_remote_root = remote_root
        self.temp_local_root = os.path.abspath(local_root)
        self.temp_remote_root = remote_root
        self.remote_profile = dict(remote_profile) if remote_profile is not None else {}

    @classmethod
    def load_from_dict(cls, context_dict: dict[str, Any]) -> "HDFSContext":  # noqa: ANN401
        local_root = context_dict["local_root"]
        remote_root = context_dict["remote_root"]
        remote_profile = context_dict.get("remote_profile", {})
        instance = cls(
            local_root=local_root,
            remote_root=remote_root,
            remote_profile=remote_profile,
        )
        return instance

    def get_job_root(self) -> str:
        return self.remote_root

    def bind_submission(self, submission: "Submission") -> None:
        self.submission = submission
        assert submission.submission_hash is not None
        self.local_root = os.path.join(self.temp_local_root, submission.work_base)
        self.remote_root = os.path.join(
            self.temp_remote_root, submission.submission_hash
        )

        HDFS.mkdir(self.remote_root)

    def _put_files(self, files: list[str], dereference: bool = True) -> None:
        assert self.submission.submission_hash is not None
        of = self.submission.submission_hash + "_upload.tgz"
        # local tar
        if os.path.isfile(os.path.join(self.local_root, of)):
            os.remove(os.path.join(self.local_root, of))
        with tarfile.open(
            os.path.join(self.local_root, of), "w:gz", dereference=dereference
        ) as tar:
            for ii in files:
                ii_full = os.path.join(self.local_root, ii)
                tar.add(ii_full, arcname=ii)

        # trans
        from_f = os.path.join(self.local_root, of)
        HDFS.copy_from_local(os.path.join(self.local_root, of), self.remote_root)

        # clean up
        os.remove(from_f)

    def upload(self, submission: "Submission", dereference: bool = True) -> None:
        """Upload forward files and forward command files to HDFS root dir.

        Parameters
        ----------
        submission : Submission class instance
            represents a collection of tasks, such as forward file names
        dereference : bool
            whether to dereference symbolic links

        Returns
        -------
        none
        """
        manifest = SubmissionStagingPlan(self.local_root, submission).upload_manifest()
        if manifest.missing:
            missing = manifest.missing[0]
            raise FileNotFoundError(
                "cannot find upload file "
                + os.path.join(
                    self.local_root, missing.destination_prefix, missing.pattern
                )
            )
        resolver = PathResolver(self.local_root)
        file_list = [
            resolver.relative(entry.source)
            for entry in manifest.entries
            # Directory markers are useful for filesystem transfers but would
            # archive the entire HDFS staging root when represented by ``.``.
            if entry.source != Path(".")
        ]

        self._put_files(file_list, dereference=dereference)

    def download(
        self,
        submission: "Submission",
        check_exists: bool = False,
        mark_failure: bool = True,
        back_error: bool = False,
    ) -> None:
        """Download backward files from HDFS root dir.

        Parameters
        ----------
        submission : Submission class instance
            represents a collection of tasks, such as backward file names
        check_exists : bool
            whether to check if the file exists
        mark_failure : bool
            whether to mark the task as failed if the file does not exist
        back_error : bool
            whether to download error files

        Returns
        -------
        none
        """
        # download all hdfs files to tmp dir
        gz_dir = os.path.join(self.local_root, "tmp")
        if os.path.lexists(gz_dir):
            FileTransfer.remove(gz_dir)
        os.mkdir(os.path.join(self.local_root, "tmp"))
        try:
            try:
                rfile_tgz = (
                    f"{self.remote_root}/{submission.submission_hash}_*_download.tar.gz"
                )
                HDFS.copy_to_local(rfile_tgz, f"{self.local_root}/tmp/")
                for tgz in glob(os.path.join(self.local_root, "tmp/*_download.tar.gz")):
                    SafeArchiveExtractor(gz_dir).extract_tar(tgz)
            except HDFSMissingPathError:
                # A failed DistributedShell job does not produce an archive.
                # Optional terminated-log downloads can stop immediately;
                # marker-producing downloads continue with an empty remote
                # manifest so missing outputs are recorded consistently.
                if not check_exists:
                    raise
                if not mark_failure:
                    dlog.debug(
                        "No HDFS result archive found; skipping optional download"
                    )
                    # Release the staging directory before returning from the
                    # optional-download fast path; the ``finally`` block below
                    # remains a defensive cleanup for all other exits.
                    FileTransfer.remove(gz_dir)
                    return
                dlog.debug("No HDFS result archive found; recording missing outputs")

            manifest = SubmissionStagingPlan(
                self.local_root, submission
            ).download_manifest(
                gz_dir,
                fallback_root=self.local_root,
                include_errors=back_error,
            )
            if manifest.missing and not check_exists:
                missing = manifest.missing[0]
                raise FileNotFoundError(
                    "cannot find download file "
                    + os.path.join(gz_dir, missing.destination_prefix, missing.pattern)
                )
            if check_exists and mark_failure:
                writer = AtomicTextWriter(self.local_root)
                for missing in manifest.missing:
                    writer.write(missing.failure_marker(), "")
            FileTransfer(self.local_root, move=True).apply(manifest)
        finally:
            shutil.rmtree(gz_dir, ignore_errors=True)

    def check_file_exists(self, fname: str) -> bool:
        """Check whether the given file exists, often used in checking whether the belonging job has finished.

        Parameters
        ----------
        fname : string
            file name to be checked

        Returns
        -------
        status: boolean
        """
        return HDFS.exists(self._remote_file(fname))

    def clean(self) -> None:
        HDFS.remove(self.remote_root)

    def write_file(self, fname: str, write_str: str) -> str:
        normalized = PathPolicy.normalize_relative(fname)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".dpdispatcher", delete=False
        ) as fp:
            fp.write(write_str)
            local_file = fp.name
        try:
            HDFS.copy_from_local(local_file, self._remote_file(normalized))
        finally:
            FileTransfer.remove(local_file)
        return local_file

    def read_file(self, fname: str) -> bytes:
        return HDFS.read_hdfs_file(self._remote_file(fname))

    def _remote_file(self, fname: str) -> str:
        """Resolve a metadata path without allowing it to escape the HDFS root."""
        normalized = PathPolicy.normalize_relative(fname)
        return f"{self.remote_root.rstrip('/')}/{normalized}"

    def block_call(self, cmd: str) -> NoReturn:
        raise RuntimeError(
            "Unsupported method. You may use an unsupported combination of the machine and the context."
        )
