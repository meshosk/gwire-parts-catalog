"""Shared JSON serialization, file revisions and atomic writes."""

import hashlib
import json
import os
import tempfile


def revision(raw):
    return hashlib.sha256(raw).hexdigest()


def atomic_write(path, raw):
    """Replace inside the mounted directory, without leaving partial JSON."""
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, path.stat().st_mode & 0o777 if path.exists() else 0o644)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
