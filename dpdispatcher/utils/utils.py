import base64
import hashlib
import hmac
import os
import struct
import subprocess
import time
from typing import TYPE_CHECKING, Callable, Optional, Type, Union

from dpdispatcher.dlog import dlog

if TYPE_CHECKING:
    from dpdispatcher import Resources


def get_sha256(filename):
    """Get sha256 of a file.

    Parameters
    ----------
    filename : str
        The filename.

    Returns
    -------
    sha256: str
        The sha256.
    """
    h = hashlib.sha256()
    # buffer size: 128 kB
    b = bytearray(128 * 1024)
    mv = memoryview(b)
    with open(filename, "rb", buffering=0) as f:
        for n in iter(lambda: f.readinto(mv), 0):
            h.update(mv[:n])
    sha256 = h.hexdigest()
    return sha256


def hotp(key: str, period: int, token_length: int = 6, digest="sha1"):
    key_ = base64.b32decode(key.upper() + "=" * ((8 - len(key)) % 8))
    period_ = struct.pack(">Q", period)
    mac = hmac.new(key_, period_, digest).digest()
    offset = mac[-1] & 0x0F
    binary = struct.unpack(">L", mac[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(binary)[-token_length:].zfill(token_length)


def generate_totp(secret: str, period: int = 30, token_length: int = 6) -> str:
    """Generate time-based one time password (TOTP) from the secret.

    Some HPCs use TOTP for two-factor authentication for safety.

    Parameters
    ----------
    secret : str
        The encoded secret provided by the HPC. It's usually extracted
        from a 2D code and base32 encoded.
    period : int, default=30
        Time period where the code is valid in seconds.
    token_length : int, default=6
        The token length.

    Returns
    -------
    token: str
        The generated token.

    References
    ----------
    https://github.com/lepture/otpauth/blob/49914d83d36dbcd33c9e26f65002b21ce09a6303/otpauth.py#L143-L160
    """
    digest = "sha1"
    return hotp(secret, int(time.time() / period), token_length, digest)


def run_cmd_with_all_output(cmd, shell=True):
    with subprocess.Popen(
        cmd, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ) as proc:
        out, err = proc.communicate()
        ret = proc.returncode
    return (ret, out, err)


def rsync(
    from_file: str,
    to_file: str,
    port: int = 22,
    key_filename: Optional[str] = None,
    timeout: Union[int, float] = 10,
    jump_hostname: Optional[str] = None,
    jump_username: Optional[str] = None,
    jump_port: int = 22,
    jump_key_filename: Optional[str] = None,
    proxy_command: Optional[str] = None,
):
    """Call rsync to transfer files.

    Parameters
    ----------
    from_file : str
        SRC
    to_file : str
        DEST
    port : int, default=22
        port for ssh
    key_filename : str, optional
        identity file name
    timeout : int, default=10
        timeout for ssh
    jump_hostname : str, optional
        hostname or IP of SSH jump host (legacy, use proxy_command instead)
    jump_username : str, optional
        username for SSH jump host (legacy, use proxy_command instead)
    jump_port : int, default=22
        port for SSH jump host (legacy, use proxy_command instead)
    jump_key_filename : str, optional
        key filename for SSH jump host (legacy, use proxy_command instead)
    proxy_command : str, optional
        Direct ProxyCommand to use for SSH connection

    Raises
    ------
    RuntimeError
        when return code is not 0
    """
    ssh_cmd = [
        "ssh",
        "-o",
        "ConnectTimeout=" + str(timeout),
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-p",
        str(port),
        "-q",
    ]
    if key_filename is not None:
        ssh_cmd.extend(["-i", key_filename])
    
    # Handle proxy command configuration
    if proxy_command is not None and any([jump_hostname, jump_username, jump_port != 22, jump_key_filename]):
        raise ValueError("Cannot specify both 'proxy_command' and individual jump host parameters")
    
    # Use proxy_command if provided
    if proxy_command is not None:
        ssh_cmd.extend(["-o", f"ProxyCommand={proxy_command}"])
    # Otherwise, build proxy command from jump host parameters for backward compatibility
    elif jump_hostname is not None and jump_username is not None:
        proxy_cmd_parts = [
            "ssh",
            "-W", "%h:%p",  # %h and %p will be replaced by target host and port
            "-o", "StrictHostKeyChecking=no",
            "-o", f"ConnectTimeout={timeout}",
            "-p", str(jump_port),
        ]
        
        if jump_key_filename is not None:
            proxy_cmd_parts.extend(["-i", jump_key_filename])
        
        proxy_cmd_parts.append(f"{jump_username}@{jump_hostname}")
        proxy_command_built = " ".join(proxy_cmd_parts)
        ssh_cmd.extend(["-o", f"ProxyCommand={proxy_command_built}"])
    cmd = [
        "rsync",
        # -a: archieve
        # -z: compress
        "-az",
        "-e",
        " ".join(ssh_cmd),
        "-q",
        from_file,
        to_file,
    ]
    ret, out, err = run_cmd_with_all_output(cmd, shell=False)
    if ret != 0:
        raise RuntimeError(f"Failed to run {cmd}: {err}")


class RetrySignal(Exception):
    """Exception to give a signal to retry the function."""


def retry(
    max_retry: int = 3,
    sleep: Union[int, float] = 60,
    catch_exception: Type[BaseException] = RetrySignal,
) -> Callable:
    """Retry the function until it succeeds or fails for certain times.

    Parameters
    ----------
    max_retry : int, default=3
        The maximum retry times. If None, it will retry forever.
    sleep : int or float, default=60
        The sleep time in seconds.
    catch_exception : Exception, default=Exception
        The exception to catch.

    Returns
    -------
    decorator: Callable
        The decorator.

    Examples
    --------
    >>> @retry(max_retry=3, sleep=60, catch_exception=RetrySignal)
    ... def func():
    ...     raise RetrySignal("Failed")
    """

    def decorator(func):
        assert max_retry > 0, "max_retry must be greater than 0"

        def wrapper(*args, **kwargs):
            current_retry = 0
            errors = []
            while max_retry is None or current_retry < max_retry:
                try:
                    return func(*args, **kwargs)
                except (catch_exception,) as e:
                    errors.append(e)
                    dlog.exception("Failed to run %s: %s", func.__name__, e)
                    # sleep certain seconds
                    dlog.warning("Sleep %s s and retry...", sleep)
                    time.sleep(sleep)
                    current_retry += 1
            else:
                # raise all exceptions
                raise RuntimeError(
                    f"Failed to run {func.__name__} for {current_retry} times"
                ) from errors[-1]

        return wrapper

    return decorator


def customized_script_header_template(
    filename: os.PathLike, resources: "Resources"
) -> str:
    with open(filename) as f:
        template = f.read()
    return template.format(**resources.serialize())
