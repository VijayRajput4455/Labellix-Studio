#!/usr/bin/env python
import json
import os
import sys
import time
import unittest
from unittest.mock import patch

__author__ = 'TzuTaLin'

dir_name = os.path.abspath(os.path.dirname(__file__))
libs_path = os.path.join(dir_name, '..', 'libs')
sys.path.insert(0, libs_path)
from constants import SETTING_APP_MODE, SETTING_CLASSIFICATION_EXPORT_DIR
from settings import Settings

class TestSettings(unittest.TestCase):

    class QSize(object):
        def __init__(self, w, h):
            self._w = w
            self._h = h

        def width(self):
            return self._w

        def height(self):
            return self._h

    class QPoint(object):
        def __init__(self, x, y):
            self._x = x
            self._y = y

        def x(self):
            return self._x

        def y(self):
            return self._y

    class QByteArray(object):
        def __init__(self, raw):
            self._raw = raw

        def toBase64(self):
            return self._raw

    class QColor(object):
        def __init__(self, r, g, b, a):
            self._rgba = (r, g, b, a)

        def getRgb(self):
            return self._rgba

    class LabelFileFormat(object):
        def __init__(self, name):
            self.name = name

    def test_basic(self):
        settings = Settings()
        settings['test0'] = 'hello'
        settings['test1'] = 10
        settings['test2'] = [0, 2, 3]
        settings[SETTING_CLASSIFICATION_EXPORT_DIR] = '/tmp/exported-dataset'
        settings[SETTING_APP_MODE] = 'classification'
        self.assertEqual(settings.get('test3', 3), 3)
        self.assertEqual(settings.save(), True)

        settings.load()
        self.assertEqual(settings.get('test0'), 'hello')
        self.assertEqual(settings.get('test1'), 10)
        self.assertEqual(settings.get(SETTING_CLASSIFICATION_EXPORT_DIR), '/tmp/exported-dataset')
        self.assertEqual(settings.get(SETTING_APP_MODE), 'classification')

        settings.reset()

    def test_saves_schema_envelope(self):
        settings = Settings()
        settings[SETTING_APP_MODE] = 'classification'
        self.assertEqual(settings.save(), True)

        with open(settings.path, 'r', encoding='utf-8') as handle:
            payload = json.load(handle)

        self.assertEqual(payload.get('schemaVersion'), Settings.SCHEMA_VERSION)
        self.assertIsInstance(payload.get('data'), dict)
        self.assertEqual(payload.get('data', {}).get(SETTING_APP_MODE), 'classification')
        settings.reset()

    def test_migrates_unwrapped_json_payload(self):
        settings = Settings()
        legacy_payload = {
            SETTING_CLASSIFICATION_EXPORT_DIR: '/tmp/legacy-export',
            SETTING_APP_MODE: 'classification',
        }
        with open(settings.path, 'w', encoding='utf-8') as handle:
            json.dump(legacy_payload, handle)

        self.assertEqual(settings.load(), True)
        self.assertEqual(settings.get(SETTING_CLASSIFICATION_EXPORT_DIR), '/tmp/legacy-export')
        self.assertEqual(settings.get(SETTING_APP_MODE), 'classification')

        with open(settings.path, 'r', encoding='utf-8') as handle:
            migrated_payload = json.load(handle)
        self.assertEqual(migrated_payload.get('schemaVersion'), Settings.SCHEMA_VERSION)
        self.assertEqual(migrated_payload.get('data', {}).get(SETTING_APP_MODE), 'classification')
        settings.reset()

    def test_load_invalid_json_reports_paths(self):
        settings = Settings()
        with open(settings.path, 'w', encoding='utf-8') as handle:
            handle.write('{"invalid":')

        with patch('builtins.print') as mocked_print:
            self.assertEqual(settings.load(), False)

        self.assertTrue(mocked_print.called)
        printed_message = mocked_print.call_args[0][0]
        self.assertIn('Loading settings failed', printed_message)
        self.assertIn(settings.path, printed_message)
        settings.reset()

    def test_sanitizes_non_json_serializable_during_migration(self):
        settings = Settings()

        # Test the sanitization function directly with non-JSON-serializable data
        # Simulate pickle data that includes non-serializable objects
        legacy_data = {
            'valid_string': 'hello',
            'valid_int': 42,
            'non_serializable': object(),  # object() is not JSON serializable
            'nested_dict': {
                'inner_valid': 'world',
            },
            'nested_list': [1, 2, 3],
        }

        # Run sanitization
        sanitized = Settings._sanitize_for_json(legacy_data)

        # Sanitized data should only contain serializable items
        self.assertEqual(sanitized['valid_string'], 'hello')
        self.assertEqual(sanitized['valid_int'], 42)
        # Non-serializable should be missing
        self.assertNotIn('non_serializable', sanitized)

        # Nested data should be preserved where serializable
        self.assertEqual(sanitized['nested_dict']['inner_valid'], 'world')

        # Nested list should only contain serializable items
        self.assertEqual(sanitized['nested_list'], [1, 2, 3])

        # Verify the sanitized data is JSON serializable
        json_str = json.dumps(sanitized)
        self.assertIsInstance(json_str, str)

    def test_save_filters_non_json_serializable_values(self):
        settings = Settings()
        settings['safe_key'] = 'ok'
        settings['bad_key'] = object()

        self.assertEqual(settings.save(), True)

        with open(settings.path, 'r', encoding='utf-8') as handle:
            payload = json.load(handle)

        data = payload.get('data', {})
        self.assertEqual(data.get('safe_key'), 'ok')
        self.assertNotIn('bad_key', data)
        settings.reset()

    def test_save_preserves_qt_like_values_as_json_safe(self):
        settings = Settings()
        settings['window/size'] = self.QSize(1200, 700)
        settings['window/position'] = self.QPoint(30, 40)
        settings['window/state'] = self.QByteArray(b'c3RhdGU=')
        settings['line/color'] = self.QColor(1, 2, 3, 255)
        settings['labelFileFormat'] = self.LabelFileFormat('PASCAL_VOC')

        self.assertEqual(settings.save(), True)

        with open(settings.path, 'r', encoding='utf-8') as handle:
            payload = json.load(handle)

        data = payload.get('data', {})
        self.assertIn('window/size', data)
        self.assertIn('window/position', data)
        self.assertIn('window/state', data)
        self.assertIn('line/color', data)
        self.assertIn('labelFileFormat', data)

        reloaded = Settings()
        self.assertEqual(reloaded.load(), True)
        self.assertTrue(reloaded.get('window/size') is not None)
        self.assertTrue(reloaded.get('window/position') is not None)
        self.assertTrue(reloaded.get('window/state') is not None)
        self.assertTrue(reloaded.get('line/color') is not None)
        self.assertTrue(reloaded.get('labelFileFormat') is not None)
        reloaded.reset()
        


if __name__ == '__main__':
    unittest.main()
