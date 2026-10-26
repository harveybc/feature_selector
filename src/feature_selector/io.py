"""Strict JSON, content identities and durable single-writer output."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError('DUPLICATE_JSON_KEY: ' + key)
            out[key] = value
        return out
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs,
                      parse_constant=lambda v: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(canonical(value) + b'\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class RunStore:
    def __init__(self, root):
        self.root = Path(root).resolve()

    @contextmanager
    def lock(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / '.lock').open('a') as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError('RUN_ALREADY_ACTIVE') from exc
            try:
                yield self
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def save(self, name, value):
        atomic(self.root / name, value)

    def immutable(self, name, value):
        path = self.root / name
        if path.exists():
            if read(path) != value:
                raise ValueError('IMMUTABLE_RESULT_CHANGED: ' + name)
        else:
            self.save(name, value)

    def cache(self, name):
        path = self.root / name
        if not path.exists():
            return None
        envelope = read(path)
        if digest(envelope['payload']) != envelope['sha256']:
            raise ValueError('CACHE_DIGEST_MISMATCH: ' + name)
        return envelope['payload']

    def retain(self, name, payload):
        self.immutable(name, dict(sha256=digest(payload), payload=payload))
