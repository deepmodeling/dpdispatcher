"""Execute jobs locally while staging them in a separate directory."""

from __future__ import annotations

import os
import shutil
import subprocess as sp
import tempfile
from subprocess import TimeoutExpired
from typing import TYPE_CHECKING, Any

from dargs import Argument

from dpdispatcher.base_context import BaseContext
from dpdispatcher.file_manager import (
    AtomicTextWriter,
    FileTransfer,
    PathResolver,
    SubmissionStagingPlan,
)

if TYPE_CHECKING:
    from dpdispatcher.submission import Submission


class SPRetObj:
    """Adapt subprocess byte output to the stream interface used by contexts."""

    def __init__(self, ret: bytes) -> None:
        self.data = ret

    def read(self) -> bytes:
        return self.data

    def readlines(self) -> list[str]:
        lines = self.data.decode("utf-8").splitlines()
        ret = []
        for aa in lines:
            ret.append(aa + "\n")
        return ret


def _check_file_path(fname: str) -> None:
    """Create parent directories for the compatibility copy helpers."""
    dirname = os.path.dirname(fname)
    if dirname != "":
        os.makedirs(dirname, exist_ok=True)


class LocalContext(BaseContext):
    """Run jobs in the local server and remote directory.

    Parameters
    ----------
    local_root : str
        The local directory to store the jobs.
    remote_root : str
        The remote directory to store the jobs.
    remote_profile : dict, optional
        The remote profile. The default is {}.
    *args
        The arguments.
    **kwargs
        The keyword arguments.
    """

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
        self.temp_remote_root = os.path.abspath(remote_root)
        remote_profile = {} if remote_profile is None else remote_profile
        self.remote_profile = dict(remote_profile)
        self.symlink = remote_profile.get("symlink", True)

    @classmethod
    def load_from_dict(cls, context_dict: dict[str, Any]) -> LocalContext:  # noqa: ANN401
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

    def bind_submission(self, submission: Submission) -> None:
        self.submission = submission
        assert submission.submission_hash is not None
        self.local_root = os.path.join(self.temp_local_root, submission.work_base)
        self.remote_root = os.path.join(
            self.temp_remote_root, submission.submission_hash
        )

    def _copy_from_local_to_remote(self, local_path: str, remote_path: str) -> None:
        """Copy one local path to a remote path, replacing any old entry.

        This low-level helper remains for callers that used the historical
        retry-upload API. Normal submission staging goes through
        :class:`FileTransfer` and ``SubmissionStagingPlan``.
        """
        if not os.path.exists(local_path):
            raise FileNotFoundError(
                f"cannot find uploaded file {os.path.join(local_path)}"
            )
        # ``lexists`` also finds broken symlinks, which must be unlinked before
        # copying instead of accidentally following their missing target.
        if os.path.lexists(remote_path):
            if os.path.isdir(remote_path) and not os.path.islink(remote_path):
                shutil.rmtree(remote_path)
            else:
                os.remove(remote_path)
        _check_file_path(remote_path)

        if self.symlink:
            os.symlink(local_path, remote_path)
        elif os.path.isfile(local_path):
            shutil.copyfile(local_path, remote_path)
        elif os.path.isdir(local_path):
            shutil.copytree(local_path, remote_path)
        else:
            raise ValueError(f"Unknown file type: {local_path}")

    def _copy_missing_from_local_to_remote(
        self, local_path: str, remote_path: str
    ) -> None:
        """Atomically add missing paths without replacing existing entries.

        Kept as a compatibility primitive for retry code and integrations that
        need to publish a shared directory concurrently. The regular upload
        path uses the object-oriented transfer manifest instead.
        """
        if os.path.lexists(remote_path):
            if (
                os.path.isdir(local_path)
                and os.path.isdir(remote_path)
                and not os.path.islink(remote_path)
            ):
                for name in os.listdir(local_path):
                    self._copy_missing_from_local_to_remote(
                        os.path.join(local_path, name),
                        os.path.join(remote_path, name),
                    )
            return
        if not os.path.exists(local_path):
            raise FileNotFoundError(
                f"cannot find uploaded file {os.path.join(local_path)}"
            )

        _check_file_path(remote_path)
        if self.symlink:
            try:
                os.symlink(local_path, remote_path)
            except FileExistsError:
                pass
            return

        remote_dir = os.path.dirname(remote_path) or "."
        if os.path.isfile(local_path):
            descriptor, staged_path = tempfile.mkstemp(
                prefix=".dpdispatcher-", dir=remote_dir
            )
            os.close(descriptor)
            try:
                shutil.copyfile(local_path, staged_path)
                try:
                    os.link(staged_path, remote_path)
                except FileExistsError:
                    pass
            finally:
                if os.path.exists(staged_path):
                    os.remove(staged_path)
        elif os.path.isdir(local_path):
            stage_root = tempfile.mkdtemp(prefix=".dpdispatcher-", dir=remote_dir)
            staged_path = os.path.join(stage_root, "payload")
            try:
                shutil.copytree(local_path, staged_path)
                try:
                    os.rename(staged_path, remote_path)
                except OSError:
                    if not os.path.lexists(remote_path):
                        raise
            finally:
                shutil.rmtree(stage_root, ignore_errors=True)
        else:
            raise ValueError(f"Unknown file type: {local_path}")

    def upload(self, submission: Submission) -> None:
        """Stage all forward files through one validated transfer manifest."""
        os.makedirs(self.remote_root, exist_ok=True)
        plan = SubmissionStagingPlan(self.local_root, submission)
        preserve_common = getattr(
            submission, "preserve_existing_forward_common_files", False
        )
        if preserve_common:
            manifests = (
                plan.upload_manifest(include_common=False),
                plan.upload_manifest(include_tasks=False),
            )
        else:
            manifests = (plan.upload_manifest(),)
        for index, manifest in enumerate(manifests):
            if manifest.missing:
                missing = manifest.missing[0]
                raise FileNotFoundError(
                    "cannot find upload file "
                    + os.path.join(
                        self.local_root, missing.destination_prefix, missing.pattern
                    )
                )
            FileTransfer(
                self.remote_root,
                symlink=self.symlink,
                link_sources=self.symlink,
                overwrite=not (preserve_common and index == 1),
            ).apply(manifest)

    def download(
        self,
        submission: Submission,
        check_exists: bool = False,
        mark_failure: bool = True,
        back_error: bool = False,
    ) -> None:
        """Download requested artifacts through a manifest and one copier."""
        manifest = SubmissionStagingPlan(self.local_root, submission).download_manifest(
            self.remote_root,
            fallback_root=self.local_root,
            include_errors=back_error,
        )
        if manifest.missing and not check_exists:
            missing = manifest.missing[0]
            raise FileNotFoundError(
                "cannot find download file "
                + os.path.join(
                    self.remote_root, missing.destination_prefix, missing.pattern
                )
            )
        if check_exists and mark_failure:
            writer = AtomicTextWriter(self.local_root)
            for missing in manifest.missing:
                writer.write(missing.failure_marker(), "")
        FileTransfer(self.local_root, move=True).apply(manifest)

    def block_call(self, cmd: str) -> tuple[int, None, SPRetObj, SPRetObj]:
        proc = sp.Popen(
            cmd, cwd=self.remote_root, shell=True, stdout=sp.PIPE, stderr=sp.PIPE
        )
        o, e = proc.communicate()
        stdout = SPRetObj(o)
        stderr = SPRetObj(e)
        code = proc.returncode
        return code, None, stdout, stderr

    def clean(self) -> None:
        FileTransfer.remove(self.remote_root)

    def write_file(self, fname: str, write_str: str) -> None:
        AtomicTextWriter(self.remote_root).write(fname, write_str)

    def read_file(self, fname: str) -> str:
        with open(
            PathResolver(self.remote_root).resolve(fname, allow_absolute=True),
            encoding="utf-8",
        ) as fp:
            ret = fp.read()
        return ret

    def check_file_exists(self, fname: str) -> bool:
        return (
            PathResolver(self.remote_root).resolve(fname, allow_absolute=True).is_file()
        )

    def call(self, cmd: str) -> sp.Popen:
        proc = sp.Popen(
            cmd, cwd=self.remote_root, shell=True, stdout=sp.PIPE, stderr=sp.PIPE
        )
        return proc

    def check_finish(self, proc: sp.Popen) -> bool:
        return proc.poll() is not None

    def get_return(
        self, proc: sp.Popen
    ) -> tuple[int | None, SPRetObj | None, SPRetObj | None]:
        ret = proc.poll()
        if ret is None:
            return None, None, None
        else:
            try:
                o, e = proc.communicate()
                stdout = SPRetObj(o)
                stderr = SPRetObj(e)
            except TimeoutExpired:
                stdout = None
                stderr = None
        return ret, stdout, stderr

    @classmethod
    def machine_subfields(cls) -> list[Argument]:
        """Generate the machine subfields.

        Returns
        -------
        list[Argument]
            machine subfields
        """
        doc_remote_profile = "Options controlling how files are staged between local_root and remote_root when both paths are on the local filesystem."
        return [
            Argument(
                "remote_profile",
                dict,
                optional=True,
                doc=doc_remote_profile,
                sub_fields=[
                    Argument(
                        "symlink",
                        bool,
                        optional=True,
                        default=True,
                        doc="Whether to use symbolic links instead of copying files from local_root into remote_root. Disable this when the execution side cannot access the original local path through the same filesystem view.",
                    ),
                ],
            )
        ]
