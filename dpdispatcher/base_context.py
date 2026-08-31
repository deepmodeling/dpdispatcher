"""Define the execution-context interface used by machine backends."""

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from dargs import Argument

from dpdispatcher.dlog import dlog

if TYPE_CHECKING:
    from dpdispatcher.machine import Machine
    from dpdispatcher.submission import Submission


class BaseContext(metaclass=ABCMeta):
    """Define file transfer and command execution for an environment.

    ``BaseContext`` acts as both an abstract interface and a factory. Calling it
    with ``context_type`` selects a registered subclass such as ``SSHContext``
    or ``LazyLocalContext``. Concrete contexts must implement file transfer,
    cleanup, file access, and blocking command execution.
    """

    subclasses_dict = {}
    options = set()
    # alias: for subclasses_dict key
    # notes: this attribute can be inherited
    alias: tuple[str, ...] = tuple()
    init_local_root: str
    init_remote_root: str | None
    temp_local_root: str
    temp_remote_root: str
    local_root: str
    remote_root: str
    remote_profile: dict[str, Any]
    create_remote_root: bool
    submission: Submission
    machine: Machine
    # Whether completion tags can be queried through ``check_file_exists``.
    # Cloud backends expose job metadata rather than task work directories and
    # therefore recover whole completed jobs from the persisted record instead.
    supports_task_completion_tags: bool = True
    # Cloud contexts retrieve one archive per parent job; filesystem contexts
    # can select backward files directly at task granularity.
    downloads_by_job: ClassVar[bool] = False
    # Cloud contexts populate this with relative files extracted by their most
    # recent download so mixed-state cleanup never guesses at local paths.
    last_downloaded_files: set[str]
    # Some job-archive backends only create an archive when every task in the
    # grouped job succeeds.  Such backends cannot download a mixed-state job
    # by selecting only its finished sibling tasks.
    supports_partial_job_download: ClassVar[bool] = True

    def __new__(cls, *args: Any, **kwargs: Any) -> BaseContext:  # noqa: ANN401
        """Select a registered context subclass when called on ``BaseContext``."""
        if cls is BaseContext:
            subcls = cls.subclasses_dict[kwargs["context_type"]]
            instance = subcls.__new__(subcls, *args, **kwargs)
        else:
            instance = object.__new__(cls)
        return instance

    def __init_subclass__(cls, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init_subclass__(**kwargs)
        alias = [cls.__name__, *cls.alias]
        for aa in alias:
            cls.subclasses_dict[aa] = cls
            cls.subclasses_dict[aa.lower()] = cls
            cls.subclasses_dict[aa.replace("Context", "")] = cls
            cls.subclasses_dict[aa.lower().replace("context", "")] = cls
        cls.options.add(cls.__name__)

    @classmethod
    def load_from_dict(cls, context_dict: dict[str, Any]) -> BaseContext:  # noqa: ANN401
        """Create a registered context from a machine configuration mapping."""
        context_type = context_dict["context_type"]
        # print("debug778:context_type", cls.subclasses_dict, context_type)
        try:
            context_class = cls.subclasses_dict[context_type]
        except KeyError as e:
            dlog.error(
                f"KeyError:context_type; context_type:{context_type}; cls.subclasses_dict:{cls.subclasses_dict}"
            )
            raise e
        context = context_class.load_from_dict(context_dict)
        return context

    def bind_submission(self, submission: Submission) -> None:
        """Bind a submission and its derived working paths to this context."""
        self.submission = submission

    @abstractmethod
    def upload(self, submission: Submission) -> None:
        """Upload all files required by a submission to the execution root."""
        raise NotImplementedError("abstract method")

    @abstractmethod
    def download(
        self,
        submission: Submission,
        check_exists: bool = False,
        mark_failure: bool = True,
        back_error: bool = False,
    ) -> Any:  # noqa: ANN401
        """Download declared result files from the execution root."""
        raise NotImplementedError("abstract method")

    @abstractmethod
    def clean(self) -> Any:  # noqa: ANN401
        """Remove the submission-specific execution directory."""
        raise NotImplementedError("abstract method")

    @abstractmethod
    def write_file(self, fname: str, write_str: str) -> Any:  # noqa: ANN401
        """Write text to a file relative to the execution root."""
        raise NotImplementedError("abstract method")

    @abstractmethod
    def read_file(self, fname: str) -> Any:  # noqa: ANN401
        """Read text from a file relative to the execution root."""
        raise NotImplementedError("abstract method")

    def write_local_file(self, fname: str, write_str: str) -> Any:  # noqa: ANN401
        """Write a backend-local staging file when the context supports it."""
        raise NotImplementedError("context does not support local staging files")

    @abstractmethod
    def check_file_exists(self, fname: str) -> bool:
        """Return whether a file exists in the active execution root."""
        raise NotImplementedError("abstract method")

    def check_finish(self, proc: Any) -> Any:  # noqa: ANN401
        """Return whether an asynchronous process has finished."""
        raise NotImplementedError("abstract method")

    def block_checkcall(
        self, cmd: str, asynchronously: bool = False
    ) -> tuple[Any, Any, Any]:  # noqa: ANN401
        """Run command with arguments. Wait for command to complete.

        Parameters
        ----------
        cmd : str
            The command to run.
        asynchronously : bool, optional, default=False
            Run command asynchronously. If True, `nohup` will be used to run the command.

        Returns
        -------
        stdin
            standard inout
        stdout
            standard output
        stderr
            standard error

        Raises
        ------
        RuntimeError
            when the return code is not zero
        """
        if asynchronously:
            cmd = f"nohup {cmd} >/dev/null &"
        exit_status, stdin, stdout, stderr = self.block_call(cmd)
        if exit_status != 0:
            raise RuntimeError(
                "Get error code {} in calling {} with job: {} . message: {}".format(
                    exit_status,
                    cmd,
                    self.submission.submission_hash,
                    stderr.read().decode("utf-8"),
                )
            )
        return stdin, stdout, stderr

    @abstractmethod
    def block_call(self, cmd: str) -> tuple[int, Any, Any, Any]:  # noqa: ANN401
        """Run command with arguments. Wait for command to complete.

        Parameters
        ----------
        cmd : str
            The command to run.

        Returns
        -------
        exit_status
            exit code
        stdin
            standard inout
        stdout
            standard output
        stderr
            standard error
        """

    @classmethod
    def machine_arginfo(cls) -> Argument:
        """Generate the machine arginfo.

        Returns
        -------
        Argument
            machine arginfo
        """
        alias = []
        for aa in cls.alias:
            alias.extend(
                (
                    aa,
                    aa.lower(),
                    aa.replace("Context", ""),
                    aa.lower().replace("context", ""),
                )
            )
        return Argument(
            cls.__name__,
            dict,
            sub_fields=cls.machine_subfields(),
            alias=[
                cls.__name__.lower(),
                cls.__name__.replace("Context", ""),
                cls.__name__.lower().replace("context", ""),
                *alias,
            ],
        )

    @classmethod
    def machine_subfields(cls) -> list[Argument]:
        """Generate the machine subfields.

        Returns
        -------
        list[Argument]
            machine subfields
        """
        doc_remote_profile = "The information used to maintain the connection with remote machine. This field is empty for this context."
        return [Argument("remote_profile", dict, optional=True, doc=doc_remote_profile)]
