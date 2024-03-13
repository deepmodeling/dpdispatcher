# /usr/bin/python

import os

from dpdispatcher.utils.utils import run_cmd_with_all_output


class HDFS:
    """Fundamental class for HDFS basic manipulation."""

    @staticmethod
    def exists(uri):
        """Check existence of hdfs uri
        Returns: True on exists
        Raises: RuntimeError.
        """
        cmd = f"hadoop fs -test -e {uri}"
        try:
            ret, out, err = run_cmd_with_all_output(cmd)
            if ret == 0:
                return True
            elif ret == 1:
                return False
            else:
                raise RuntimeError(
                    f"Cannot check existence of hdfs uri[{uri}] "
                    f"with cmd[{cmd}]; ret[{ret}] stdout[{out}] stderr[{err}]"
                )
        except Exception as e:
            raise RuntimeError(
                f"Cannot check existence of hdfs uri[{uri}] " f"with cmd[{cmd}]"
            ) from e

    @staticmethod
    def remove(uri):
        """Check existence of hdfs uri
        Returns: True on exists
        Raises: RuntimeError.
        """
        cmd = f"hadoop fs -rm -r {uri}"
        try:
            ret, out, err = run_cmd_with_all_output(cmd)
            if ret == 0:
                return True
            else:
                raise RuntimeError(
                    f"Cannot remove hdfs uri[{uri}] "
                    f"with cmd[{cmd}]; ret[{ret}] output[{out}] stderr[{err}]"
                )
        except Exception as e:
            raise RuntimeError(
                f"Cannot remove hdfs uri[{uri}] " f"with cmd[{cmd}]"
            ) from e

    @staticmethod
    def mkdir(uri):
        """Make new hdfs directory
        Returns: True on success
        Raises: RuntimeError.
        """
        cmd = f"hadoop fs -mkdir -p {uri}"
        try:
            ret, out, err = run_cmd_with_all_output(cmd)
            if ret == 0:
                return True
            else:
                raise RuntimeError(
                    f"Cannot mkdir of hdfs uri[{uri}] "
                    f"with cmd[{cmd}]; ret[{ret}] output[{out}] stderr[{err}]"
                )
        except Exception as e:
            raise RuntimeError(
                f"Cannot mkdir of hdfs uri[{uri}] " f"with cmd[{cmd}]"
            ) from e

    @staticmethod
    def copy_from_local(local_path, to_uri):
        """Returns: True on success
        Raises: on unexpected error.
        """
        # Make sure local_path is accessible
        if not os.path.exists(local_path) or not os.access(local_path, os.R_OK):
            raise RuntimeError(f"try to access local_path[{local_path}] " "but failed")
        cmd = f"hadoop fs -copyFromLocal -f {local_path} {to_uri}"
        try:
            ret, out, err = run_cmd_with_all_output(cmd)
            if ret == 0:
                return True, out
            else:
                raise RuntimeError(
                    f"Cannot copy local[{local_path}] to remote[{to_uri}] with cmd[{cmd}]; "
                    f"ret[{ret}] output[{out}] stderr[{err}]"
                )
        except Exception as e:
            raise RuntimeError(
                f"Cannot copy local[{local_path}] to remote[{to_uri}] with cmd[{cmd}]"
            ) from e

    @staticmethod
    def copy_to_local(from_uri, local_path):
        remote = ""
        if isinstance(from_uri, str):
            remote = from_uri
        elif isinstance(from_uri, list) or isinstance(from_uri, tuple):
            remote = " ".join(from_uri)
        cmd = f"hadoop fs -copyToLocal {remote} {local_path}"

        try:
            ret, out, err = run_cmd_with_all_output(cmd)
            if ret == 0:
                return True
            else:
                raise RuntimeError(
                    f"Cannot copy remote[{from_uri}] to local[{local_path}] with cmd[{cmd}]; "
                    f"ret[{ret}] output[{out}] stderr[{err}]"
                )
        except Exception as e:
            raise RuntimeError(
                f"Cannot copy remote[{from_uri}] to local[{local_path}] with cmd[{cmd}]"
            ) from e

    @staticmethod
    def read_hdfs_file(uri):
        cmd = f"hadoop fs -text {uri}"
        try:
            ret, out, err = run_cmd_with_all_output(cmd)
            if ret == 0:
                return out
            else:
                raise RuntimeError(
                    f"Cannot read text from uri[{uri}]"
                    f"cmd [{cmd}] ret[{ret}] output[{out}] stderr[{err}]"
                )
        except Exception as e:
            raise RuntimeError(
                f"Cannot read text from uri[{uri}]" f"cmd [{cmd}]"
            ) from e

    @staticmethod
    def move(from_uri, to_uri):
        cmd = f"hadoop fs -mv {from_uri} {to_uri}"
        try:
            ret, out, err = run_cmd_with_all_output(cmd)
            if ret == 0:
                return True
            else:
                raise RuntimeError(
                    f"Cannot move from_uri[{from_uri}] to "
                    f"to_uri[{to_uri}] with cmd[{cmd}]; "
                    f"ret[{ret}] output[{out}] stderr[{err}]"
                )
        except Exception as e:
            raise RuntimeError(
                f"Cannot move from_uri[{from_uri}] to "
                f"to_uri[{to_uri}] with cmd[{cmd}]"
            ) from e
