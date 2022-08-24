import hashlib
import time
import struct
import hmac
import base64
import subprocess
from typing import Callable, Union

from dpdispatcher import dlog

def get_sha256(filename):
    """Get sha256 of a file.
    
    Parameters
    ----------
    filename: str
        The filename.

    Returns
    -------
    sha256: str
        The sha256.
    """
    h = hashlib.sha256()
    # buffer size: 128 kB
    b = bytearray(128*1024)
    mv = memoryview(b)
    with open(filename, 'rb', buffering=0) as f:
        for n in iter(lambda: f.readinto(mv), 0):
            h.update(mv[:n])
    sha256 = h.hexdigest()
    return sha256

def hotp(key: str, period: int, token_length: int=6, digest='sha1'):
    key = base64.b32decode(key.upper() + '=' * ((8 - len(key)) % 8))
    period = struct.pack('>Q', period)
    mac = hmac.new(key, period, digest).digest()
    offset = mac[-1] & 0x0f
    binary = struct.unpack('>L', mac[offset:offset+4])[0] & 0x7fffffff
    return str(binary)[-token_length:].zfill(token_length)

def generate_totp(secret: str, period: int=30, token_length: int=6) -> str:
    """Generate time-based one time password (TOTP) from the secret.

    Some HPCs use TOTP for two-factor authentication for safety.

    Parameters
    ----------
    secret: str
        The encoded secret provided by the HPC. It's usually extracted
        from a 2D code and base32 encoded.
    period: int, default=30
        Time period where the code is valid in seconds.
    token_length: int, default=6
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
    with subprocess.Popen(cmd, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
        out, err = proc.communicate()
        ret = proc.returncode
    return (ret, out, err)


def rsync(from_file: str, to_file: str):
    """Call rsync to transfer files.
    
    Parameters
    ----------
    from_file: str
        SRC
    to_file: str
        DEST
    
    Raises
    ------
    RuntimeError
        when return code is not 0
    """
    cmd = [
        'rsync',
        # -a: archieve
        # -z: compress
        '-az',
        from_file,
        to_file,
    ]
    ret, out, err = run_cmd_with_all_output(cmd, shell=False)
    if ret != 0:
        raise RuntimeError("Failed to run %s: %s" %(cmd, err))


class RetrySignal(Exception):
    """Exception to give a signal to retry the function."""


def retry(max_retry: int = 3, sleep: Union[int, float] = 60, catch_exception: BaseException = RetrySignal) -> Callable:
    """Retry the function until it succeeds or fails for certain times.

    Parameters
    ----------
    max_retry: int, default=3
        The maximum retry times. If None, it will retry forever.
    sleep: int or float, default=60
        The sleep time in seconds.
    catch_exception: Exception, default=Exception
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
                except catch_exception as e:
                    errors.append(e)
                    dlog.exception("Failed to run %s: %s", func.__name__, e)
                    # sleep certain seconds
                    dlog.warning("Sleep %s s and retry...", sleep)
                    time.sleep(sleep)
                    current_retry += 1
            else:
                # raise all exceptions
                raise RuntimeError("Failed to run %s for %d times" %(func.__name__, current_retry)) from errors[-1]
        return wrapper
    return decorator
