import json
import logging
import os
import shutil
import time

from libs.atomic_io import atomic_write_json
from libs.io_validation import (
    ensure_directory,
    ensure_distinct_directories,
    ensure_output_is_directory_or_create,
    ensure_path_within_root,
    ensure_relative_path,
    ensure_required_path,
)


LOGGER = logging.getLogger(__name__)


class ClassificationIOError(Exception):
    pass


class ClassificationSession(object):
    VERSION = 1
    MANIFEST_FILENAME = '.labellix_classification.json'

    def __init__(self, source_dir=None, classes=None, labels=None):
        self.source_dir = source_dir
        self.classes = list(classes or [])
        self.labels = dict(labels or {})

    @staticmethod
    def default_manifest_path(source_dir):
        return os.path.join(source_dir, ClassificationSession.MANIFEST_FILENAME)

    @classmethod
    def load(cls, manifest_path):
        if not manifest_path or not os.path.exists(manifest_path):
            return cls()

        try:
            with open(manifest_path, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
        except Exception as exc:
            LOGGER.exception('Failed to load classification manifest from %s', manifest_path)
            raise ClassificationIOError('Failed to load classification manifest from %s: %s' % (manifest_path, exc))

        return cls(
            source_dir=data.get('source_dir'),
            classes=data.get('classes', []),
            labels=data.get('labels', {}),
        )

    def save(self, manifest_path):
        directory = os.path.dirname(manifest_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        payload = {
            'version': self.VERSION,
            'saved_at': int(time.time()),
            'source_dir': self.source_dir,
            'classes': sorted(set(self.classes)),
            'labels': self.labels,
        }

        try:
            atomic_write_json(manifest_path, payload, encoding='utf-8', indent=2, sort_keys=True)
        except Exception as exc:
            LOGGER.exception('Failed to save classification manifest to %s', manifest_path)
            raise ClassificationIOError('Failed to save classification manifest to %s: %s' % (manifest_path, exc))

    def export_dataset(self, output_dir, move_images=True):
        ensure_required_path(
            self.source_dir,
            ClassificationIOError,
            'Missing source directory for classification export.',
        )
        ensure_directory(
            self.source_dir,
            ClassificationIOError,
            'Source directory does not exist: %s' % self.source_dir,
        )
        ensure_required_path(
            output_dir,
            ClassificationIOError,
            'Missing export directory for classification export.',
        )
        source_root, _ = ensure_distinct_directories(
            self.source_dir,
            output_dir,
            ClassificationIOError,
            'Export directory must be different from source directory.',
        )
        ensure_output_is_directory_or_create(
            output_dir,
            ClassificationIOError,
            'Export path exists and is not a directory: %s' % output_dir,
        )

        exported_files = []
        for relative_path, class_name in sorted(self.labels.items()):
            if not class_name or not str(class_name).strip():
                raise ClassificationIOError('Invalid class name for path %s' % relative_path)
            if os.path.sep in class_name or (os.path.altsep and os.path.altsep in class_name):
                raise ClassificationIOError('Class name cannot contain path separators: %s' % class_name)
            ensure_relative_path(
                relative_path,
                ClassificationIOError,
                'Label path must be relative: %s' % relative_path,
            )
            source_path = os.path.join(self.source_dir, relative_path)
            ensure_path_within_root(
                source_path,
                source_root,
                ClassificationIOError,
                'Label path escapes source directory: %s' % relative_path,
            )
            if not os.path.exists(source_path):
                raise ClassificationIOError('Source image not found: %s' % source_path)

            class_dir = os.path.join(output_dir, class_name)
            if not os.path.exists(class_dir):
                os.makedirs(class_dir)

            target_path = self._unique_target_path(class_dir, os.path.basename(source_path))
            if move_images:
                shutil.move(source_path, target_path)
            else:
                shutil.copy2(source_path, target_path)
            exported_files.append(target_path)

        return exported_files

    @staticmethod
    def _unique_target_path(directory, filename):
        base, ext = os.path.splitext(filename)
        candidate = os.path.join(directory, filename)
        suffix = 1
        while os.path.exists(candidate):
            candidate = os.path.join(directory, '%s_%d%s' % (base, suffix, ext))
            suffix += 1
        return candidate
