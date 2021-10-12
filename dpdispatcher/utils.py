import hashlib
import time
import struct
import hmac
import base64
import subprocess

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


def generate_totp(secret: str, period: int=30, token_length: int=6) -> int:
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
    token: int
        The generated token.

    References
    ----------
    https://github.com/lepture/otpauth/blob/49914d83d36dbcd33c9e26f65002b21ce09a6303/otpauth.py#L143-L160
    """
    timestamp = time.time()
    counter = int(timestamp) // period
    msg = struct.pack('>Q', counter)
    digest = hmac.new(base64.b32decode(secret), msg, hashlib.sha1).digest()
    ob = digest[19]
    pos = ob & 15
    base = struct.unpack('>I', digest[pos:pos + 4])[0] & 0x7fffffff
    token = base % (10**token_length)
    return str(token).zfill(token_length)

def run_cmd_with_all_output(cmd):
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    ret = proc.returncode
    return (ret, out, err)