# /usr/bin/python

import os
import shlex
from typing import List, Sequence, Tuple, Union

from dpdispatcher.utils.utils import run_cmd_with_all_output


def _command_text(command: Sequence[str]) -> str:
    """Format an argv command for diagnostics without executing a shell."""
    return " ".join(shlex.quote(argument) for argument in command)


def _run_hadoop(command: List[str]) -> Tuple[int, bytes, bytes]:
    """Run one Hadoop command without allowing shell interpretation."""
    return run_cmd_with_all_output(command, shell=False)


def _validate_operand(value: str, name: str) -> str:
    """Reject values that Hadoop could parse as options or invalid argv data."""
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value:
        raise ValueError(f"{name} must not be empty")
    if "\x00" in value:
        raise ValueError(f"{name} must not contain NUL characters")
    if value.startswith("-"):
        raise ValueError(f"{name} must not begin with '-'")
    return value


class HDFS:
    """Provide basic HDFS filesystem operations through the Hadoop CLI.

    Path and URI operands are passed literally without shell expansion.  Callers
    that need local ``~`` expansion must resolve it before invoking these helpers.
    """

    @staticmethod
    def exists(uri: str) -> bool:
        """Return whether an HDFS URI exists.

        Parameters
        ----------
        uri : str
            HDFS URI to inspect.

        Raises
        ------
        RuntimeError
            If Hadoop returns an unexpected status or cannot be executed.
        """
        uri = _validate_operand(uri, "uri")
        command = ["hadoop", "fs", "-test", "-e", uri]
        command_text = _command_text(command)
        try:
            ret, out, err = _run_hadoop(command)
            if ret == 0:
                return True
            if ret == 1:
                return False
            raise RuntimeError(
                f"Cannot check existence of hdfs uri[{uri}] "
                f"with cmd[{command_text}]; ret[{ret}] stdout[{out}] stderr[{err}]"
            )
        except Exception as error:
            raise RuntimeError(
                f"Cannot check existence of hdfs uri[{uri}] with cmd[{command_text}]"
            ) from error

    @staticmethod
    def remove(uri: str) -> bool:
        """Remove an HDFS URI recursively."""
        uri = _validate_operand(uri, "uri")
        command = ["hadoop", "fs", "-rm", "-r", uri]
        command_text = _command_text(command)
        try:
            ret, out, err = _run_hadoop(command)
            if ret == 0:
                return True
            raise RuntimeError(
                f"Cannot remove hdfs uri[{uri}] "
                f"with cmd[{command_text}]; ret[{ret}] output[{out}] stderr[{err}]"
            )
        except Exception as error:
            raise RuntimeError(
                f"Cannot remove hdfs uri[{uri}] with cmd[{command_text}]"
            ) from error

    @staticmethod
    def mkdir(uri: str) -> bool:
        """Create an HDFS directory and any missing parents."""
        uri = _validate_operand(uri, "uri")
        command = ["hadoop", "fs", "-mkdir", "-p", uri]
        command_text = _command_text(command)
        try:
            ret, out, err = _run_hadoop(command)
            if ret == 0:
                return True
            raise RuntimeError(
                f"Cannot mkdir of hdfs uri[{uri}] "
                f"with cmd[{command_text}]; ret[{ret}] output[{out}] stderr[{err}]"
            )
        except Exception as error:
            raise RuntimeError(
                f"Cannot mkdir of hdfs uri[{uri}] with cmd[{command_text}]"
            ) from error

    @staticmethod
    def copy_from_local(local_path: str, to_uri: str) -> Tuple[bool, bytes]:
        """Copy one readable local path to HDFS, replacing an existing file."""
        local_path = _validate_operand(local_path, "local_path")
        to_uri = _validate_operand(to_uri, "to_uri")
        if not os.path.exists(local_path) or not os.access(local_path, os.R_OK):
            raise RuntimeError(f"try to access local_path[{local_path}] but failed")
        command = ["hadoop", "fs", "-copyFromLocal", "-f", local_path, to_uri]
        command_text = _command_text(command)
        try:
            ret, out, err = _run_hadoop(command)
            if ret == 0:
                return True, out
            raise RuntimeError(
                f"Cannot copy local[{local_path}] to remote[{to_uri}] with cmd[{command_text}]; "
                f"ret[{ret}] output[{out}] stderr[{err}]"
            )
        except Exception as error:
            raise RuntimeError(
                f"Cannot copy local[{local_path}] to remote[{to_uri}] with cmd[{command_text}]"
            ) from error

    @staticmethod
    def copy_to_local(
        from_uri: Union[str, List[str], Tuple[str, ...]], local_path: str
    ) -> bool:
        """Copy one or more HDFS URIs to a local path."""
        if isinstance(from_uri, str):
            remote_arguments = [_validate_operand(from_uri, "from_uri")]
        elif isinstance(from_uri, (list, tuple)):
            if not from_uri:
                raise ValueError("from_uri must contain at least one HDFS URI")
            remote_arguments = [_validate_operand(uri, "from_uri") for uri in from_uri]
        else:
            raise TypeError("from_uri must be a string, list, or tuple of strings")
        local_path = _validate_operand(local_path, "local_path")

        command = [
            "hadoop",
            "fs",
            "-copyToLocal",
            *remote_arguments,
            local_path,
        ]
        command_text = _command_text(command)
        try:
            ret, out, err = _run_hadoop(command)
            if ret == 0:
                return True
            raise RuntimeError(
                f"Cannot copy remote[{from_uri}] to local[{local_path}] with cmd[{command_text}]; "
                f"ret[{ret}] output[{out}] stderr[{err}]"
            )
        except Exception as error:
            raise RuntimeError(
                f"Cannot copy remote[{from_uri}] to local[{local_path}] with cmd[{command_text}]"
            ) from error

    @staticmethod
    def read_hdfs_file(uri: str) -> bytes:
        """Read an HDFS file through ``hadoop fs -text``."""
        uri = _validate_operand(uri, "uri")
        command = ["hadoop", "fs", "-text", uri]
        command_text = _command_text(command)
        try:
            ret, out, err = _run_hadoop(command)
            if ret == 0:
                return out
            raise RuntimeError(
                f"Cannot read text from uri[{uri}]"
                f"cmd [{command_text}] ret[{ret}] output[{out}] stderr[{err}]"
            )
        except Exception as error:
            raise RuntimeError(
                f"Cannot read text from uri[{uri}]cmd [{command_text}]"
            ) from error

    @staticmethod
    def move(from_uri: str, to_uri: str) -> bool:
        """Move an HDFS URI to another HDFS URI."""
        from_uri = _validate_operand(from_uri, "from_uri")
        to_uri = _validate_operand(to_uri, "to_uri")
        command = ["hadoop", "fs", "-mv", from_uri, to_uri]
        command_text = _command_text(command)
        try:
            ret, out, err = _run_hadoop(command)
            if ret == 0:
                return True
            raise RuntimeError(
                f"Cannot move from_uri[{from_uri}] to "
                f"to_uri[{to_uri}] with cmd[{command_text}]; "
                f"ret[{ret}] output[{out}] stderr[{err}]"
            )
        except Exception as error:
            raise RuntimeError(
                f"Cannot move from_uri[{from_uri}] to to_uri[{to_uri}] with cmd[{command_text}]"
            ) from error
