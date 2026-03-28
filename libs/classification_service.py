import os

from libs.classification_io import ClassificationSession


class ClassificationService(object):
    @staticmethod
    def _normalize_label(value):
        if value is None:
            return ''
        return str(value).strip()

    def resolve_source_dir(self, dir_name=None, file_path=None, last_open_dir=None):
        if dir_name and os.path.isdir(dir_name):
            return dir_name
        if file_path:
            return os.path.dirname(file_path)
        if last_open_dir and os.path.isdir(last_open_dir):
            return last_open_dir
        return None

    def load_manifest_state(self, source_dir, base_label_hist=None):
        state = {
            'manifest_path': None,
            'label_hist': list(base_label_hist or []),
            'classification_labels': {},
        }

        if not source_dir or not os.path.isdir(source_dir):
            return state

        manifest_path = ClassificationSession.default_manifest_path(source_dir)
        session = ClassificationSession.load(manifest_path)

        state['manifest_path'] = manifest_path
        state['label_hist'] = self._merge_labels(state['label_hist'], session.classes)
        state['classification_labels'] = self._absolute_existing_labels(source_dir, session.labels)
        return state

    def save_manifest(self, source_dir, manifest_path, label_hist, classification_labels):
        labels = self._manifest_relative_labels(source_dir, classification_labels)
        session = ClassificationSession(source_dir=source_dir, classes=label_hist, labels=labels)
        session.save(manifest_path)
        return manifest_path

    def assign_label(self, file_path, label, label_hist, classification_labels):
        if not file_path:
            return None

        normalized = self._normalize_label(label)
        if not normalized:
            return None

        if normalized not in label_hist:
            return None

        classification_labels[file_path] = normalized
        return normalized

    @staticmethod
    def clear_label(file_path, classification_labels):
        if file_path in classification_labels:
            del classification_labels[file_path]
            return True
        return False

    @staticmethod
    def next_unlabeled_index(image_paths, classification_labels, start_index=0):
        for index in range(max(start_index, 0), len(image_paths)):
            image_path = image_paths[index]
            if not classification_labels.get(image_path):
                return index
        return None

    def build_export_session(self, source_dir, label_hist, classification_labels):
        labels = self._manifest_relative_labels(source_dir, classification_labels)
        return ClassificationSession(source_dir=source_dir, classes=label_hist, labels=labels)

    def _merge_labels(self, existing_labels, session_classes):
        merged = list(existing_labels or [])
        normalized = sorted({
            self._normalize_label(label)
            for label in (session_classes or [])
            if self._normalize_label(label)
        }, key=lambda value: value.lower())
        for label in normalized:
            if label not in merged:
                merged.append(label)
        return merged

    @staticmethod
    def _absolute_existing_labels(source_dir, labels):
        resolved = {}
        for relative_path, label in (labels or {}).items():
            absolute_path = os.path.abspath(os.path.join(source_dir, relative_path))
            if os.path.exists(absolute_path):
                resolved[absolute_path] = label
        return resolved

    @staticmethod
    def _manifest_relative_labels(source_dir, classification_labels):
        labels = {}
        source_root = os.path.abspath(source_dir)
        for image_path, label in (classification_labels or {}).items():
            if not label:
                continue

            image_abs = os.path.abspath(image_path)
            try:
                common = os.path.commonpath([image_abs, source_root])
            except ValueError:
                continue
            if common != source_root:
                continue

            relative_path = os.path.relpath(image_abs, source_root)
            labels[relative_path] = label
        return labels