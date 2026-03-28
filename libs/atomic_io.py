import json
import logging
import os
import tempfile


LOGGER = logging.getLogger(__name__)


def _ensure_parent_dir(path):
    directory = os.path.dirname(os.path.abspath(path))
    if directory and not os.path.exists(directory):
        os.makedirs(directory)


def atomic_write_bytes(path, data):
    """Write bytes atomically via temp file + os.replace."""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError('atomic_write_bytes expects bytes-like data')

    _ensure_parent_dir(path)
    directory = os.path.dirname(os.path.abspath(path)) or '.'
    fd, tmp_path = tempfile.mkstemp(prefix='.tmp-', dir=directory)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception as exc:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        LOGGER.exception('Atomic bytes write failed for %s', path)
        raise OSError('Atomic bytes write failed for %s: %s' % (path, exc))


def atomic_write_text(path, content, encoding='utf-8'):
    """Write text atomically via temp file + os.replace."""
    if not isinstance(content, str):
        raise TypeError('atomic_write_text expects str content')

    _ensure_parent_dir(path)
    directory = os.path.dirname(os.path.abspath(path)) or '.'
    fd, tmp_path = tempfile.mkstemp(prefix='.tmp-', dir=directory)
    try:
        with os.fdopen(fd, 'w', encoding=encoding) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception as exc:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        LOGGER.exception('Atomic text write failed for %s', path)
        raise OSError('Atomic text write failed for %s: %s' % (path, exc))


def atomic_write_json(path, payload, encoding='utf-8', indent=2, sort_keys=True):
    """Serialize and write JSON atomically."""
    content = json.dumps(payload, indent=indent, sort_keys=sort_keys)
    atomic_write_text(path, content + '\n', encoding=encoding)
