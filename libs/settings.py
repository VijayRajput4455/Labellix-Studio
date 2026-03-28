import os
import json
import logging

from libs.atomic_io import atomic_write_json


LOGGER = logging.getLogger(__name__)


class Settings(object):
    SCHEMA_VERSION = 1
    KEY_SCHEMA_VERSION = 'schemaVersion'
    KEY_DATA = 'data'
    _SKIP = object()

    def __init__(self):
        # By default, settings are stored in the user's home for Labellix Studio.
        home = os.path.expanduser("~")
        self.data = {}
        self.path = os.path.join(home, '.labellixStudioSettings.json')

    def __setitem__(self, key, value):
        self.data[key] = value

    def __getitem__(self, key):
        return self.data[key]

    def get(self, key, default=None):
        if key in self.data:
            return self.data[key]
        return default

    def save(self):
        if self.path:
            # Filter non-JSON runtime objects (e.g., QColor) before persisting.
            sanitized_data = self._sanitize_for_json(self.data)
            self.data = sanitized_data
            payload = {
                self.KEY_SCHEMA_VERSION: self.SCHEMA_VERSION,
                self.KEY_DATA: sanitized_data,
            }
            atomic_write_json(self.path, payload, encoding='utf-8', indent=2, sort_keys=True)
            return True
        return False

    @staticmethod
    def _is_json_serializable(obj):
        """Check if an object is JSON serializable."""
        if obj is None or isinstance(obj, (bool, int, float, str)):
            return True
        if isinstance(obj, (list, tuple)):
            return all(Settings._is_json_serializable(item) for item in obj)
        if isinstance(obj, dict):
            return all(isinstance(k, str) and Settings._is_json_serializable(v) for k, v in obj.items())
        return False

    @staticmethod
    def _qt_types():
        """Lazily resolve Qt classes used in settings serialization."""
        try:
            from PyQt5.QtCore import QSize, QPoint, QByteArray
            from PyQt5.QtGui import QColor
            return {
                'QSize': QSize,
                'QPoint': QPoint,
                'QByteArray': QByteArray,
                'QColor': QColor,
            }
        except Exception:
            try:
                from PyQt4.QtCore import QSize, QPoint, QByteArray
                from PyQt4.QtGui import QColor
                return {
                    'QSize': QSize,
                    'QPoint': QPoint,
                    'QByteArray': QByteArray,
                    'QColor': QColor,
                }
            except Exception:
                return {}

    @staticmethod
    def _encode_special_value(value):
        """Convert known runtime-only objects to JSON-safe envelopes."""
        type_name = type(value).__name__

        if type_name == 'QSize' and hasattr(value, 'width') and hasattr(value, 'height'):
            return {
                '__qt_type__': 'QSize',
                'w': int(value.width()),
                'h': int(value.height()),
            }

        if type_name == 'QPoint' and hasattr(value, 'x') and hasattr(value, 'y'):
            return {
                '__qt_type__': 'QPoint',
                'x': int(value.x()),
                'y': int(value.y()),
            }

        if type_name == 'QByteArray':
            try:
                b64 = bytes(value.toBase64()).decode('ascii')
                return {
                    '__qt_type__': 'QByteArray',
                    'base64': b64,
                }
            except Exception:
                return None

        if type_name == 'QColor' and hasattr(value, 'getRgb'):
            try:
                r, g, b, a = value.getRgb()
                return {
                    '__qt_type__': 'QColor',
                    'rgba': [int(r), int(g), int(b), int(a)],
                }
            except Exception:
                return None

        if type_name == 'LabelFileFormat' and hasattr(value, 'name'):
            return {
                '__enum__': 'LabelFileFormat',
                'name': value.name,
            }

        return None

    @staticmethod
    def _decode_special_value(data):
        """Restore known serialized envelopes back to runtime objects."""
        if not isinstance(data, dict):
            return data

        qt_type = data.get('__qt_type__')
        if qt_type:
            qt = Settings._qt_types()
            qt_class = qt.get(qt_type)

            if qt_type == 'QSize':
                w = int(data.get('w', 0))
                h = int(data.get('h', 0))
                return qt_class(w, h) if qt_class else {'w': w, 'h': h}

            if qt_type == 'QPoint':
                x = int(data.get('x', 0))
                y = int(data.get('y', 0))
                return qt_class(x, y) if qt_class else {'x': x, 'y': y}

            if qt_type == 'QByteArray':
                b64 = data.get('base64', '')
                if qt_class and hasattr(qt_class, 'fromBase64'):
                    try:
                        return qt_class.fromBase64(b64.encode('ascii'))
                    except Exception:
                        return qt_class()
                return b64

            if qt_type == 'QColor':
                rgba = data.get('rgba', [0, 0, 0, 255])
                if isinstance(rgba, (list, tuple)) and len(rgba) == 4:
                    r, g, b, a = [int(v) for v in rgba]
                    return qt_class(r, g, b, a) if qt_class else [r, g, b, a]
                return data

        enum_type = data.get('__enum__')
        if enum_type == 'LabelFileFormat':
            enum_name = data.get('name')
            if not enum_name:
                return data
            try:
                from libs.labelFile import LabelFileFormat
                return LabelFileFormat[enum_name]
            except Exception:
                return enum_name

        return data

    @staticmethod
    def _sanitize_for_json(data):
        """Remove or convert non-JSON-serializable objects (e.g., QColor from PyQt).
        
        Recursively walks the data structure and:
        - Removes dict/list entries whose values are not JSON-serializable
        - Logs what was filtered
        """
        if data is None or isinstance(data, (bool, int, float, str)):
            return data

        encoded = Settings._encode_special_value(data)
        if encoded is not None:
            return encoded

        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if not isinstance(key, str):
                    LOGGER.warning('Skipped non-string setting key (type=%s)', type(key).__name__)
                    continue
                if isinstance(value, dict):
                    child = Settings._sanitize_for_json(value)
                    if child is not Settings._SKIP:
                        sanitized[key] = child
                elif isinstance(value, (list, tuple)):
                    child = Settings._sanitize_for_json(list(value))
                    if child is not Settings._SKIP:
                        sanitized[key] = child
                elif Settings._is_json_serializable(value):
                    sanitized[key] = value
                else:
                    child = Settings._sanitize_for_json(value)
                    if child is Settings._SKIP:
                        LOGGER.warning('Skipped non-serializable setting: %s (type=%s)', key, type(value).__name__)
                    else:
                        sanitized[key] = child
            return sanitized

        if isinstance(data, (list, tuple)):
            sanitized = []
            for item in data:
                if isinstance(item, dict):
                    child = Settings._sanitize_for_json(item)
                    if child is not Settings._SKIP:
                        sanitized.append(child)
                elif isinstance(item, (list, tuple)):
                    child = Settings._sanitize_for_json(item)
                    if child is not Settings._SKIP:
                        sanitized.append(child)
                elif Settings._is_json_serializable(item):
                    sanitized.append(item)
                else:
                    child = Settings._sanitize_for_json(item)
                    if child is Settings._SKIP:
                        LOGGER.warning('Skipped non-serializable list item (type=%s)', type(item).__name__)
                    else:
                        sanitized.append(child)
            return sanitized

        return Settings._SKIP

    @staticmethod
    def _deserialize_for_runtime(data):
        """Recursively restore serialized envelopes to runtime values."""
        if isinstance(data, list):
            return [Settings._deserialize_for_runtime(item) for item in data]

        if isinstance(data, dict):
            restored_special = Settings._decode_special_value(data)
            if restored_special is not data:
                return restored_special
            return {
                key: Settings._deserialize_for_runtime(value)
                for key, value in data.items()
            }

        return data

    def _extract_data_from_json_payload(self, payload):
        # Current schema: {"schemaVersion": <int>, "data": {..settings..}}
        if (
            isinstance(payload, dict)
            and self.KEY_SCHEMA_VERSION in payload
            and self.KEY_DATA in payload
        ):
            schema_version = payload.get(self.KEY_SCHEMA_VERSION)
            data = payload.get(self.KEY_DATA)
            if not isinstance(schema_version, int):
                raise ValueError('Invalid settings schemaVersion')
            if not isinstance(data, dict):
                raise ValueError('Invalid settings data payload')
            # Future migrations can be added here when SCHEMA_VERSION increments.
            if schema_version > self.SCHEMA_VERSION:
                raise ValueError('Unsupported settings schemaVersion: {0}'.format(schema_version))
            return self._deserialize_for_runtime(data)

        # Backward compatibility: previously the JSON root was the settings dict directly.
        if isinstance(payload, dict):
            return self._deserialize_for_runtime(payload)

        raise ValueError('JSON root must be an object')

    def load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, 'r', encoding='utf-8') as f:
                    payload = json.load(f)
                self.data = self._extract_data_from_json_payload(payload)
                # Persist in latest schema envelope when loading old unwrapped JSON.
                if self.KEY_SCHEMA_VERSION not in payload:
                    self.save()
                return True
        except (OSError, json.JSONDecodeError, AttributeError, ValueError, TypeError) as exc:
            message = 'Loading settings failed (json: {0}): {1}'.format(self.path, exc)
            LOGGER.exception(message)
            print(message)
        return False

    def reset(self):
        if os.path.exists(self.path):
            os.remove(self.path)
            print('Removed setting file {0}'.format(self.path))
        self.data = {}
        self.path = None
