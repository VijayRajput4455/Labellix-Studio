import os
import tempfile
import unittest
import json

from libs.license_plate_io import (
    LicensePlateDatasetSession,
    LicensePlateIOError,
    ensure_txt_path,
    read_annotations,
    write_annotations,
)


class TestLicensePlateIO(unittest.TestCase):

    def test_ensure_txt_path(self):
        self.assertEqual('/tmp/a.txt', ensure_txt_path('/tmp/a'))
        self.assertEqual('/tmp/a.txt', ensure_txt_path('/tmp/a.txt'))

    def test_write_and_read_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            txt_path = os.path.join(tmp_dir, 'sample.txt')
            records = [
                {'plate': 'HR06AB1234', 'xmin': 10, 'ymin': 20, 'xmax': 120, 'ymax': 60},
                {'plate': 'DL8CAX9999', 'xmin': 15, 'ymin': 25, 'xmax': 100, 'ymax': 55},
            ]

            write_annotations(txt_path, records)
            loaded = read_annotations(txt_path)
            self.assertEqual(records, loaded)

    def test_read_supports_whitespace_delimited_rows(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            txt_path = os.path.join(tmp_dir, 'sample.txt')
            with open(txt_path, 'w', encoding='utf-8') as handle:
                handle.write('HR06AB1234 10 20 120 60\n')

            loaded = read_annotations(txt_path)
            self.assertEqual(1, len(loaded))
            self.assertEqual('HR06AB1234', loaded[0]['plate'])
            self.assertEqual(10, loaded[0]['xmin'])
            self.assertEqual(60, loaded[0]['ymax'])

    def test_write_rejects_empty_plate(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            txt_path = os.path.join(tmp_dir, 'sample.txt')
            with self.assertRaises(LicensePlateIOError):
                write_annotations(txt_path, [{'plate': ' ', 'xmin': 1, 'ymin': 2, 'xmax': 3, 'ymax': 4}])

    def test_read_rejects_malformed_row(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            txt_path = os.path.join(tmp_dir, 'sample.txt')
            with open(txt_path, 'w', encoding='utf-8') as handle:
                handle.write('broken_line\n')

            with self.assertRaises(LicensePlateIOError):
                read_annotations(txt_path)

    def test_export_dataset_copy(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as output_parent:
            image1 = os.path.join(source_dir, 'car1.jpg')
            image2 = os.path.join(source_dir, 'car2.jpg')
            with open(image1, 'wb') as handle:
                handle.write(b'img1')
            with open(image2, 'wb') as handle:
                handle.write(b'img2')

            write_annotations(os.path.splitext(image1)[0] + '.txt', [
                {'plate': 'HR06AB1234', 'xmin': 10, 'ymin': 20, 'xmax': 120, 'ymax': 60}
            ])

            session = LicensePlateDatasetSession(source_dir=source_dir)
            dataset_root = os.path.join(output_parent, 'lp_dataset')
            result = session.export_dataset(dataset_root, [image1, image2], move_images=False, skip_unlabeled=True)

            self.assertEqual(1, result['exported_count'])
            self.assertEqual(1, result['skipped_unlabeled'])
            self.assertTrue(os.path.isfile(os.path.join(dataset_root, 'images', 'car1.jpg')))
            self.assertTrue(os.path.isfile(os.path.join(dataset_root, 'labels', 'car1.txt')))
            self.assertTrue(os.path.isfile(result['report_path']))
            with open(result['report_path'], 'r', encoding='utf-8') as report_file:
                report = json.load(report_file)
            self.assertEqual(1, report['exported_count'])
            self.assertEqual(1, report['skipped_unlabeled'])
            self.assertFalse(report['move_images'])
            self.assertTrue(os.path.isfile(image1))
            self.assertTrue(os.path.isfile(os.path.splitext(image1)[0] + '.txt'))

    def test_export_dataset_move(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as output_parent:
            image1 = os.path.join(source_dir, 'car1.jpg')
            with open(image1, 'wb') as handle:
                handle.write(b'img1')

            label1 = os.path.splitext(image1)[0] + '.txt'
            write_annotations(label1, [
                {'plate': 'DL8CAX9999', 'xmin': 1, 'ymin': 2, 'xmax': 3, 'ymax': 4}
            ])

            session = LicensePlateDatasetSession(source_dir=source_dir)
            dataset_root = os.path.join(output_parent, 'lp_dataset')
            result = session.export_dataset(dataset_root, [image1], move_images=True, skip_unlabeled=True)

            self.assertEqual(1, result['exported_count'])
            self.assertTrue(os.path.isfile(result['report_path']))
            with open(result['report_path'], 'r', encoding='utf-8') as report_file:
                report = json.load(report_file)
            self.assertTrue(report['move_images'])
            self.assertFalse(os.path.exists(image1))
            self.assertFalse(os.path.exists(label1))
            self.assertTrue(os.path.isfile(os.path.join(dataset_root, 'images', 'car1.jpg')))
            self.assertTrue(os.path.isfile(os.path.join(dataset_root, 'labels', 'car1.txt')))


if __name__ == '__main__':
    unittest.main()
