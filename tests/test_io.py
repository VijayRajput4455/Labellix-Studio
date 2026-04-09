import os
import sys
import tempfile
import unittest


def _has_module(name):
    try:
        __import__(name)
        return True
    except ImportError:
        return False


@unittest.skipUnless(_has_module('lxml'), 'lxml is required for Pascal VOC tests')
class TestPascalVocRW(unittest.TestCase):

    def test_upper(self):
        dir_name = os.path.abspath(os.path.dirname(__file__))
        libs_path = os.path.join(dir_name, '..', 'libs')
        sys.path.insert(0, libs_path)
        from pascal_voc_io import PascalVocWriter
        from pascal_voc_io import PascalVocReader

        # Test Write/Read
        writer = PascalVocWriter('tests', 'test', (512, 512, 1), local_img_path='tests/test.512.512.bmp')
        difficult = 1
        writer.add_bnd_box(60, 40, 430, 504, 'person', difficult)
        writer.add_bnd_box(113, 40, 450, 403, 'face', difficult)
        writer.save('tests/test.xml')

        reader = PascalVocReader('tests/test.xml')
        shapes = reader.get_shapes()

        person_bnd_box = shapes[0]
        face = shapes[1]
        self.assertEqual(person_bnd_box[0], 'person')
        self.assertEqual(person_bnd_box[1], [(60, 40), (430, 40), (430, 504), (60, 504)])
        self.assertEqual(face[0], 'face')
        self.assertEqual(face[1], [(113, 40), (450, 40), (450, 403), (113, 403)])



@unittest.skipUnless(_has_module('PyQt5'), 'PyQt5 is required for CreateML tests')
class TestCreateMLRW(unittest.TestCase):

    def test_a_write(self):
        dir_name = os.path.abspath(os.path.dirname(__file__))
        libs_path = os.path.join(dir_name, '..', 'libs')
        sys.path.insert(0, libs_path)
        from create_ml_io import CreateMLWriter

        person = {'label': 'person', 'points': ((65, 45), (420, 45), (420, 512), (65, 512))}
        face = {'label': 'face', 'points': ((245, 250), (350, 250), (350, 365), (245, 365))}

        expected_width = 105    # 350-245 -> create_ml_io.py ll 46
        expected_height = 115   # 365-250 -> create_ml_io.py ll 49
        expected_x = 297.5      # 245+105/2 -> create_ml_io.py ll 53
        expected_y = 307.5      # 250+115/2 > create_ml_io.py ll 54

        shapes = [person, face]
        output_file = dir_name + "/tests.json"

        writer = CreateMLWriter('tests', 'test.512.512.bmp', (512, 512, 1), shapes, output_file,
                                local_img_path='tests/test.512.512.bmp')
        
        writer.verified = True
        writer.write()

        # check written json
        with open(output_file, "r") as file:
            input_data = file.read()

        import json
        data_dict = json.loads(input_data)[0]
        self.assertEqual(True, data_dict['verified'], 'verified tag not reflected')
        self.assertEqual('test.512.512.bmp', data_dict['image'], 'filename not correct in .json')
        self.assertEqual(2, len(data_dict['annotations']), 'output file contains to less annotations')
        face = data_dict['annotations'][1]
        self.assertEqual('face', face['label'], 'label name is wrong')
        face_coords = face['coordinates']
        self.assertEqual(expected_width, face_coords['width'], 'calculated width is wrong')
        self.assertEqual(expected_height, face_coords['height'], 'calculated height is wrong')
        self.assertEqual(expected_x, face_coords['x'], 'calculated x is wrong')
        self.assertEqual(expected_y, face_coords['y'], 'calculated y is wrong')

    def test_b_read(self):
        dir_name = os.path.abspath(os.path.dirname(__file__))
        libs_path = os.path.join(dir_name, '..', 'libs')
        sys.path.insert(0, libs_path)
        from create_ml_io import CreateMLReader

        output_file = dir_name + "/tests.json"
        reader = CreateMLReader(output_file, 'tests/test.512.512.bmp')
        shapes = reader.get_shapes()
        face = shapes[1]

        self.assertEqual(2, len(shapes), 'shape count is wrong')
        self.assertEqual('face', face[0], 'label is wrong')

        face_coords = face[1]
        x_min = face_coords[0][0]
        x_max = face_coords[1][0]
        y_min = face_coords[0][1]
        y_max = face_coords[2][1]

        self.assertEqual(245, x_min, 'xmin is wrong')
        self.assertEqual(350, x_max, 'xmax is wrong')
        self.assertEqual(250, y_min, 'ymin is wrong')
        self.assertEqual(365, y_max, 'ymax is wrong')


class TestClassificationSession(unittest.TestCase):

    def test_manifest_round_trip_and_export(self):
        dir_name = os.path.abspath(os.path.dirname(__file__))
        libs_path = os.path.join(dir_name, '..', 'libs')
        sys.path.insert(0, libs_path)
        from classification_io import ClassificationSession

        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as output_dir:
            cat_image = os.path.join(source_dir, 'cat_001.jpg')
            dog_image = os.path.join(source_dir, 'dog_001.jpg')
            with open(cat_image, 'wb') as handle:
                handle.write(b'cat')
            with open(dog_image, 'wb') as handle:
                handle.write(b'dog')

            manifest_path = ClassificationSession.default_manifest_path(source_dir)
            session = ClassificationSession(
                source_dir=source_dir,
                classes=['cat', 'dog'],
                labels={'cat_001.jpg': 'cat', 'dog_001.jpg': 'dog'})
            session.save(manifest_path)

            restored = ClassificationSession.load(manifest_path)
            self.assertEqual(source_dir, restored.source_dir)
            self.assertEqual({'cat_001.jpg': 'cat', 'dog_001.jpg': 'dog'}, restored.labels)

            exported_files = restored.export_dataset(output_dir, move_images=True)
            self.assertEqual(2, len(exported_files))
            self.assertTrue(os.path.exists(os.path.join(output_dir, 'cat', 'cat_001.jpg')))
            self.assertTrue(os.path.exists(os.path.join(output_dir, 'dog', 'dog_001.jpg')))
            self.assertFalse(os.path.exists(cat_image))
            self.assertFalse(os.path.exists(dog_image))

    def test_export_rejects_same_output_dir_as_source(self):
        dir_name = os.path.abspath(os.path.dirname(__file__))
        libs_path = os.path.join(dir_name, '..', 'libs')
        sys.path.insert(0, libs_path)
        from classification_io import ClassificationSession, ClassificationIOError

        with tempfile.TemporaryDirectory() as source_dir:
            cat_image = os.path.join(source_dir, 'cat_001.jpg')
            with open(cat_image, 'wb') as handle:
                handle.write(b'cat')

            session = ClassificationSession(
                source_dir=source_dir,
                classes=['cat'],
                labels={'cat_001.jpg': 'cat'})

            with self.assertRaises(ClassificationIOError):
                session.export_dataset(source_dir, move_images=True)

    def test_manifest_load_error_includes_path(self):
        dir_name = os.path.abspath(os.path.dirname(__file__))
        libs_path = os.path.join(dir_name, '..', 'libs')
        sys.path.insert(0, libs_path)
        from classification_io import ClassificationSession, ClassificationIOError

        with tempfile.TemporaryDirectory() as source_dir:
            manifest_path = ClassificationSession.default_manifest_path(source_dir)
            with open(manifest_path, 'w', encoding='utf-8') as handle:
                handle.write('{"broken":')

            with self.assertRaises(ClassificationIOError) as ctx:
                ClassificationSession.load(manifest_path)

            self.assertIn(manifest_path, str(ctx.exception))
            self.assertIn('Failed to load classification manifest', str(ctx.exception))


class TestYOLODatasetSession(unittest.TestCase):

    def test_export_split_and_yaml_with_skips(self):
        dir_name = os.path.abspath(os.path.dirname(__file__))
        libs_path = os.path.join(dir_name, '..', 'libs')
        sys.path.insert(0, libs_path)
        from yolo_io import YOLODatasetSession

        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as output_parent:
            with open(os.path.join(source_dir, 'classes.txt'), 'w', encoding='utf-8') as classes_file:
                classes_file.write('cat\n')
                classes_file.write('dog\n')

            image_names = ['a.jpg', 'b.jpg', 'c.jpg', 'd.jpg', 'e.jpg']
            for image_name in image_names:
                with open(os.path.join(source_dir, image_name), 'wb') as image_file:
                    image_file.write(b'img')

            # Create labels for 4 images, keep one unlabeled to test skip behavior.
            labeled = ['a.txt', 'b.txt', 'c.txt', 'd.txt']
            for label_name in labeled:
                with open(os.path.join(source_dir, label_name), 'w', encoding='utf-8') as label_file:
                    label_file.write('0 0.5 0.5 0.1 0.1\n')

            session = YOLODatasetSession(source_dir=source_dir, seed=42)
            dataset_root = os.path.join(output_parent, 'dataset')
            result = session.export_dataset(
                output_dir=dataset_root,
                image_paths=[os.path.join(source_dir, name) for name in image_names],
                train_percent=80,
                test_percent=10,
                valid_percent=10,
                copy_images=True,
                skip_unlabeled=True,
                write_yaml=True)

            self.assertEqual(4, result['total_labeled'])
            self.assertEqual(1, result['skipped_unlabeled'])
            self.assertTrue(os.path.exists(os.path.join(dataset_root, 'dataset.yaml')))

            self.assertEqual(3, result['exported']['train'])
            self.assertEqual(1, result['exported']['test'] + result['exported']['valid'])

            for split in ('train', 'test', 'valid'):
                self.assertTrue(os.path.isdir(os.path.join(dataset_root, split, 'images')))
                self.assertTrue(os.path.isdir(os.path.join(dataset_root, split, 'labels')))

    def test_export_requires_classes_file(self):
        dir_name = os.path.abspath(os.path.dirname(__file__))
        libs_path = os.path.join(dir_name, '..', 'libs')
        sys.path.insert(0, libs_path)
        from yolo_io import YOLODatasetSession, YOLODatasetExportError

        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as output_parent:
            image_path = os.path.join(source_dir, 'a.jpg')
            label_path = os.path.join(source_dir, 'a.txt')
            with open(image_path, 'wb') as image_file:
                image_file.write(b'img')
            with open(label_path, 'w', encoding='utf-8') as label_file:
                label_file.write('0 0.5 0.5 0.1 0.1\n')

            session = YOLODatasetSession(source_dir=source_dir, seed=42)
            with self.assertRaises(YOLODatasetExportError):
                session.export_dataset(
                    output_dir=os.path.join(output_parent, 'dataset'),
                    image_paths=[image_path],
                    train_percent=80,
                    test_percent=10,
                    valid_percent=10,
                    copy_images=True,
                    skip_unlabeled=True,
                    write_yaml=True)

    def test_export_rejects_image_outside_source(self):
        dir_name = os.path.abspath(os.path.dirname(__file__))
        libs_path = os.path.join(dir_name, '..', 'libs')
        sys.path.insert(0, libs_path)
        from yolo_io import YOLODatasetSession, YOLODatasetExportError

        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as outside_dir, tempfile.TemporaryDirectory() as output_parent:
            with open(os.path.join(source_dir, 'classes.txt'), 'w', encoding='utf-8') as classes_file:
                classes_file.write('cat\n')

            outside_image = os.path.join(outside_dir, 'outside.jpg')
            outside_label = os.path.join(outside_dir, 'outside.txt')
            with open(outside_image, 'wb') as image_file:
                image_file.write(b'img')
            with open(outside_label, 'w', encoding='utf-8') as label_file:
                label_file.write('0 0.5 0.5 0.1 0.1\n')

            session = YOLODatasetSession(source_dir=source_dir, seed=42)
            with self.assertRaises(YOLODatasetExportError):
                session.export_dataset(
                    output_dir=os.path.join(output_parent, 'dataset'),
                    image_paths=[outside_image],
                    train_percent=80,
                    test_percent=10,
                    valid_percent=10,
                    copy_images=True,
                    skip_unlabeled=True,
                    write_yaml=True)

    def test_preview_counts_and_seeded_split(self):
        dir_name = os.path.abspath(os.path.dirname(__file__))
        libs_path = os.path.join(dir_name, '..', 'libs')
        sys.path.insert(0, libs_path)
        from yolo_io import YOLODatasetSession

        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as out1, tempfile.TemporaryDirectory() as out2:
            with open(os.path.join(source_dir, 'classes.txt'), 'w', encoding='utf-8') as classes_file:
                classes_file.write('cat\n')

            image_paths = []
            for idx in range(10):
                image_name = 'img_%02d.jpg' % idx
                label_name = 'img_%02d.txt' % idx
                image_path = os.path.join(source_dir, image_name)
                label_path = os.path.join(source_dir, label_name)
                with open(image_path, 'wb') as image_file:
                    image_file.write(b'img')
                with open(label_path, 'w', encoding='utf-8') as label_file:
                    label_file.write('0 0.5 0.5 0.1 0.1\n')
                image_paths.append(image_path)

            session1 = YOLODatasetSession(source_dir=source_dir, seed=99)
            preview = session1.preview_split(
                image_paths=image_paths,
                train_percent=80,
                test_percent=10,
                valid_percent=10,
                skip_unlabeled=True)

            self.assertEqual(10, preview['total_labeled'])
            self.assertEqual(8, preview['counts']['train'])
            self.assertEqual(1, preview['counts']['test'])
            self.assertEqual(1, preview['counts']['valid'])

            result1 = session1.export_dataset(
                output_dir=os.path.join(out1, 'dataset'),
                image_paths=image_paths,
                train_percent=80,
                test_percent=10,
                valid_percent=10,
                copy_images=True,
                skip_unlabeled=True,
                write_yaml=True)

            session2 = YOLODatasetSession(source_dir=source_dir, seed=99)
            result2 = session2.export_dataset(
                output_dir=os.path.join(out2, 'dataset'),
                image_paths=image_paths,
                train_percent=80,
                test_percent=10,
                valid_percent=10,
                copy_images=True,
                skip_unlabeled=True,
                write_yaml=True)

            self.assertEqual(result1['exported'], result2['exported'])

    def test_preview_split_without_shuffle_uses_input_order(self):
        dir_name = os.path.abspath(os.path.dirname(__file__))
        libs_path = os.path.join(dir_name, '..', 'libs')
        sys.path.insert(0, libs_path)
        from yolo_io import YOLODatasetSession

        with tempfile.TemporaryDirectory() as source_dir:
            with open(os.path.join(source_dir, 'classes.txt'), 'w', encoding='utf-8') as classes_file:
                classes_file.write('cat\n')

            image_paths = []
            for idx in range(6):
                image_name = 'img_%02d.jpg' % idx
                label_name = 'img_%02d.txt' % idx
                image_path = os.path.join(source_dir, image_name)
                label_path = os.path.join(source_dir, label_name)
                with open(image_path, 'wb') as image_file:
                    image_file.write(b'img')
                with open(label_path, 'w', encoding='utf-8') as label_file:
                    label_file.write('0 0.5 0.5 0.1 0.1\n')
                image_paths.append(image_path)

            session = YOLODatasetSession(source_dir=source_dir, seed=7)
            preview = session.preview_split(
                image_paths=image_paths,
                train_percent=50,
                test_percent=25,
                valid_percent=25,
                skip_unlabeled=True,
                shuffle=False,
            )

            split = preview['split_assignment']
            train_names = [os.path.basename(pair[0]) for pair in split['train']]
            test_names = [os.path.basename(pair[0]) for pair in split['test']]
            valid_names = [os.path.basename(pair[0]) for pair in split['valid']]

            self.assertEqual(['img_00.jpg', 'img_01.jpg', 'img_02.jpg'], train_names)
            self.assertEqual(['img_03.jpg', 'img_04.jpg'], test_names)
            self.assertEqual(['img_05.jpg'], valid_names)

    def test_preview_split_with_shuffle_changes_order(self):
        dir_name = os.path.abspath(os.path.dirname(__file__))
        libs_path = os.path.join(dir_name, '..', 'libs')
        sys.path.insert(0, libs_path)
        from yolo_io import YOLODatasetSession

        with tempfile.TemporaryDirectory() as source_dir:
            with open(os.path.join(source_dir, 'classes.txt'), 'w', encoding='utf-8') as classes_file:
                classes_file.write('cat\n')

            image_paths = []
            for idx in range(8):
                image_name = 'img_%02d.jpg' % idx
                label_name = 'img_%02d.txt' % idx
                image_path = os.path.join(source_dir, image_name)
                label_path = os.path.join(source_dir, label_name)
                with open(image_path, 'wb') as image_file:
                    image_file.write(b'img')
                with open(label_path, 'w', encoding='utf-8') as label_file:
                    label_file.write('0 0.5 0.5 0.1 0.1\n')
                image_paths.append(image_path)

            session = YOLODatasetSession(source_dir=source_dir, seed=19)
            no_shuffle = session.preview_split(
                image_paths=image_paths,
                train_percent=75,
                test_percent=25,
                valid_percent=0,
                skip_unlabeled=True,
                shuffle=False,
            )
            shuffled = session.preview_split(
                image_paths=image_paths,
                train_percent=75,
                test_percent=25,
                valid_percent=0,
                skip_unlabeled=True,
                shuffle=True,
            )

            no_shuffle_train = [os.path.basename(pair[0]) for pair in no_shuffle['split_assignment']['train']]
            shuffled_train = [os.path.basename(pair[0]) for pair in shuffled['split_assignment']['train']]

            self.assertNotEqual(no_shuffle_train, shuffled_train)


if __name__ == '__main__':
    unittest.main()
