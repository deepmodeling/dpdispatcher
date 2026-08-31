"""Stage DistributedShell submission data through HDFS archives."""

import os
import shutil
import tarfile
from glob import glob
from typing import TYPE_CHECKING, Any, NoReturn

from dpdispatcher.base_context import BaseContext
from dpdispatcher.dlog import dlog
from dpdispatcher.utils.archive import safe_extract_tar
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
        remote_profile: dict[str, Any] = {},  # noqa: ANN401
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        assert isinstance(local_root, str)
        self.init_local_root = local_root
        self.init_remote_root = remote_root
        self.temp_local_root = os.path.abspath(local_root)
        self.temp_remote_root = remote_root
        self.remote_profile = remote_profile

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

    def migrate_recovery_root(
        self,
        old_remote_root: str,
        new_remote_root: str,
        *,
        force: bool = False,
    ) -> bool:
        """Move a recovered submission tree through the HDFS API.

        Resource-only resumes must preserve completion tags stored under the
        previous hash.  Local filesystem operations cannot inspect or rename an
        HDFS URI, so use backend existence checks and an atomic HDFS move.
        Existing new-hash state wins to keep repeated recovery idempotent.

        Returns
        -------
        bool
            Whether this call moved (or, for a forced rollback, confirmed) an
            existing source root.  Recovery uses the signal to roll the move
            back if subsequent rebinding fails.

        Parameters
        ----------
        force : bool, default=False
            Treat an existing destination with no source as an already-completed
            operation and report success. Recovery passes this only while
            reversing a move, so a concurrent rollback is considered successful
            instead of being mistaken for a failed rollback.
        """
        self._last_recovery_already_at_destination = False
        if old_remote_root == new_remote_root:
            return False
        if HDFS.exists(new_remote_root):
            # A destination left by an interrupted recovery must not hide the
            # source tree that still contains completion tags.  Returning is
            # safe only when the source has already disappeared (idempotent
            # completion of an earlier move).
            if HDFS.exists(old_remote_root):
                raise FileExistsError(
                    "Cannot migrate recovered HDFS submission: both old and new "
                    f"roots exist ({old_remote_root}, {new_remote_root})"
                )
            self._last_recovery_already_at_destination = True
            return force
        if not HDFS.exists(old_remote_root):
            raise FileNotFoundError(
                f"Recovered HDFS submission root does not exist: {old_remote_root}"
            )
        HDFS.move(old_remote_root, new_remote_root)
        return True

    def rollback_recovery_root(
        self,
        current_remote_root: str,
        previous_remote_root: str,
    ) -> bool:
        """Reverse a recovery migration, tolerating an already-finished rollback.

        This dedicated hook keeps the ``force`` detail private to HDFS while
        allowing older third-party contexts that implement only the original
        two-argument migration hook to remain usable by ``Submission``.
        """
        return self.migrate_recovery_root(
            current_remote_root,
            previous_remote_root,
            force=True,
        )

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
        file_list = []

        for task in submission.belonging_tasks:
            local_job = os.path.join(self.local_root, task.task_work_path)
            for ff in task.forward_files:
                abs_file_list = glob(os.path.join(local_job, ff))
                if not abs_file_list:
                    raise FileNotFoundError(
                        "cannot find upload file " + os.path.join(local_job, ff)
                    )
                rel_file_list = [
                    os.path.relpath(ii, self.local_root) for ii in abs_file_list
                ]
                file_list.extend(rel_file_list)

        local_job = self.local_root
        for fc in submission.forward_common_files:
            abs_file_list = glob(os.path.join(local_job, fc))
            if not abs_file_list:
                raise FileNotFoundError(
                    "cannot find upload file " + os.path.join(local_job, fc)
                )
            rel_file_list = [
                os.path.relpath(ii, self.local_root) for ii in abs_file_list
            ]
            file_list.extend(rel_file_list)

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
        cwd = os.getcwd()

        # download all hdfs files to tmp dir
        gz_dir = os.path.join(self.local_root, "tmp")
        if os.path.exists(gz_dir):
            shutil.rmtree(gz_dir, ignore_errors=True)
        os.mkdir(os.path.join(self.local_root, "tmp"))
        rfile_tgz = f"{self.remote_root}/{submission.submission_hash}_*_download.tar.gz"
        lfile_tgz = f"{self.local_root}/tmp/"
        try:
            HDFS.copy_to_local(rfile_tgz, lfile_tgz)
        except HDFSMissingPathError:
            # A failed DistributedShell job does not produce an archive.  An
            # explicit terminated-log download should still succeed when no
            # optional archive exists, while normal result downloads retain
            # the original error/retry behavior.
            if check_exists and not mark_failure:
                dlog.debug("No HDFS result archive found; skipping optional download")
                shutil.rmtree(gz_dir, ignore_errors=True)
                return
            raise

        tgz_file_list = glob(os.path.join(self.local_root, "tmp/*_download.tar.gz"))
        for tgz in tgz_file_list:
            with tarfile.open(tgz, "r:gz") as tar:
                safe_extract_tar(tar, gz_dir)

        for task in submission.belonging_tasks:
            local_job = os.path.join(self.local_root, task.task_work_path)
            remote_job = os.path.join(gz_dir, task.task_work_path)
            # Work on a copy so generated error artifacts do not become part
            # of the submission's persistent backward-file configuration.
            flist = list(task.backward_files)
            if back_error:
                errors = glob(os.path.join(remote_job, "error*"))
                flist.extend(os.path.relpath(error, remote_job) for error in errors)
            for jj in flist:
                rfile = os.path.join(remote_job, jj)
                lfile = os.path.join(local_job, jj)

                if not os.path.exists(rfile):
                    if not check_exists:
                        raise FileNotFoundError("do not find download file " + rfile)
                    if mark_failure:
                        with open(
                            os.path.join(
                                self.local_root,
                                task.task_work_path,
                                f"tag_failure_download_{jj}",
                            ),
                            "w",
                        ) as fp:
                            pass
                    # Missing files are optional when mark_failure is false.
                    continue
                if os.path.exists(lfile):
                    dlog.info(f"find existing {lfile}, replacing by {rfile}")
                    if os.path.isdir(lfile):
                        shutil.rmtree(lfile, ignore_errors=True)
                    elif os.path.isfile(lfile):
                        os.remove(lfile)
                shutil.move(rfile, lfile)

        local_job = self.local_root
        remote_job = gz_dir
        flist = list(submission.backward_common_files)
        if back_error:
            errors = glob(os.path.join(remote_job, "error*"))
            flist.extend(os.path.relpath(error, remote_job) for error in errors)
        for jj in flist:
            rfile = os.path.join(remote_job, jj)
            lfile = os.path.join(local_job, jj)

            if not os.path.exists(rfile):
                if not check_exists:
                    raise FileNotFoundError("do not find download file " + rfile)
                if mark_failure:
                    with open(
                        os.path.join(self.local_root, f"tag_failure_download_{jj}"),
                        "w",
                    ) as fp:
                        pass
                # Missing files are optional when mark_failure is false.
                continue
            if os.path.exists(lfile):
                dlog.info(f"find existing {lfile}, replacing by {rfile}")
                if os.path.isdir(lfile):
                    shutil.rmtree(lfile, ignore_errors=True)
                elif os.path.isfile(lfile):
                    os.remove(lfile)
            shutil.move(rfile, lfile)

        # remove tmp dir
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
        return bool(HDFS.exists(os.path.join(self.remote_root, fname)))

    def clean(self) -> None:
        HDFS.remove(self.remote_root)

    def write_file(self, fname: str, write_str: str) -> str:
        local_file = os.path.join("/tmp/", fname)
        with open(local_file, "w") as fp:
            fp.write(write_str)
        HDFS.copy_from_local(local_file, os.path.join(self.remote_root, fname))
        return local_file

    def read_file(self, fname: str) -> bytes:
        return HDFS.read_hdfs_file(os.path.join(self.remote_root, fname))

    def block_call(self, cmd: str) -> NoReturn:
        raise RuntimeError(
            "Unsupported method. You may use an unsupported combination of the machine and the context."
        )
