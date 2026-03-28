import os
import tempfile
import unittest

from libs.classification_service import ClassificationService


class TestClassificationService(unittest.TestCase):

    def test_resolve_source_dir_priority(self):
        service = ClassificationService()
        with tempfile.TemporaryDirectory() as dir_name, tempfile.TemporaryDirectory() as last_open_dir:
            resolved = service.resolve_source_dir(
                dir_name=dir_name,
                file_path=os.path.join('/tmp', 'any.jpg'),
                last_open_dir=last_open_dir,
            )
            self.assertEqual(dir_name, resolved)

            resolved = service.resolve_source_dir(
                dir_name='/path/does/not/exist',
                file_path=os.path.join(dir_name, 'img.jpg'),
                last_open_dir=last_open_dir,
            )
            self.assertEqual(dir_name, resolved)

            resolved = service.resolve_source_dir(
                dir_name='/path/does/not/exist',
                file_path=None,
                last_open_dir=last_open_dir,
            )
            self.assertEqual(last_open_dir, resolved)

    def test_load_manifest_state_merges_classes_and_filters_missing_paths(self):
        service = ClassificationService()
        with tempfile.TemporaryDirectory() as source_dir:
            existing_img = os.path.join(source_dir, 'cat.jpg')
            missing_img = os.path.join(source_dir, 'missing.jpg')
            with open(existing_img, 'wb') as image_file:
                image_file.write(b'cat')

            from libs.classification_io import ClassificationSession
            session = ClassificationSession(
                source_dir=source_dir,
                classes=['dog', ' cat ', ''],
                labels={
                    'cat.jpg': 'cat',
                    'missing.jpg': 'dog',
                },
            )
            manifest_path = ClassificationSession.default_manifest_path(source_dir)
            session.save(manifest_path)

            state = service.load_manifest_state(source_dir, base_label_hist=['bird'])
            self.assertEqual(manifest_path, state['manifest_path'])
            self.assertEqual(['bird', 'cat', 'dog'], state['label_hist'])
            self.assertEqual({'%s' % os.path.abspath(existing_img): 'cat'}, state['classification_labels'])
            self.assertNotIn(os.path.abspath(missing_img), state['classification_labels'])

    def test_save_manifest_ignores_paths_outside_source(self):
        service = ClassificationService()
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as outside_dir:
            inside_image = os.path.join(source_dir, 'inside.jpg')
            outside_image = os.path.join(outside_dir, 'outside.jpg')
            with open(inside_image, 'wb') as image_file:
                image_file.write(b'in')
            with open(outside_image, 'wb') as image_file:
                image_file.write(b'out')

            labels = {
                inside_image: 'cat',
                outside_image: 'dog',
            }
            manifest_path = os.path.join(source_dir, '.labellix_classification.json')
            service.save_manifest(
                source_dir=source_dir,
                manifest_path=manifest_path,
                label_hist=['cat', 'dog'],
                classification_labels=labels,
            )

            from libs.classification_io import ClassificationSession
            loaded = ClassificationSession.load(manifest_path)
            self.assertEqual({'inside.jpg': 'cat'}, loaded.labels)

    def test_assign_clear_and_next_unlabeled(self):
        service = ClassificationService()
        labels = {}
        image_paths = ['a.jpg', 'b.jpg', 'c.jpg']

        self.assertIsNone(service.assign_label(None, 'cat', ['cat'], labels))
        self.assertIsNone(service.assign_label('a.jpg', ' ', ['cat'], labels))
        self.assertIsNone(service.assign_label('a.jpg', 'dog', ['cat'], labels))

        assigned = service.assign_label('a.jpg', ' cat ', ['cat'], labels)
        self.assertEqual('cat', assigned)
        self.assertEqual('cat', labels['a.jpg'])

        next_index = service.next_unlabeled_index(image_paths, labels, start_index=0)
        self.assertEqual(1, next_index)

        self.assertTrue(service.clear_label('a.jpg', labels))
        self.assertFalse(service.clear_label('a.jpg', labels))


if __name__ == '__main__':
    unittest.main()
