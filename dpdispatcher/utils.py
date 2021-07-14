import hashlib


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
