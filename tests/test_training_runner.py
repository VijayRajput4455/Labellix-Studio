import os
import sys
import tempfile
import unittest


dir_name = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.abspath(os.path.join(dir_name, '..'))
sys.path.insert(0, project_root)

from libs.training_runner import (
    TrainingCommandError,
    build_yolov8_train_command,
    format_command_for_display,
    infer_run_artifacts,
    parse_yolov8_progress_line,
)


class TestTrainingRunner(unittest.TestCase):

    def test_build_command_success(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            yaml_path = os.path.join(tmp_dir, 'dataset.yaml')
            with open(yaml_path, 'w', encoding='utf-8') as handle:
                handle.write('path: .\n')

            command = build_yolov8_train_command(
                data_yaml=yaml_path,
                output_dir=tmp_dir,
                run_name='exp01',
                model_size='medium',
                epochs=50,
                batch_size=16,
                image_size=640,
                patience=20,
                device='0',
                workers=4,
                cli_executable='yolo',
                extra_args='cache=True')

            self.assertIn('model=yolov8m.pt', command)
            self.assertIn('epochs=50', command)
            self.assertIn('batch=16', command)
            self.assertIn('cache=True', command)

    def test_build_command_requires_yaml(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(TrainingCommandError):
                build_yolov8_train_command(
                    data_yaml=os.path.join(tmp_dir, 'missing.yaml'),
                    output_dir=tmp_dir,
                    run_name='exp01',
                    model_size='nano',
                    epochs=10,
                    batch_size=4,
                    image_size=640,
                    patience=5)

    def test_build_command_rejects_invalid_numeric_values(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            yaml_path = os.path.join(tmp_dir, 'dataset.yaml')
            with open(yaml_path, 'w', encoding='utf-8') as handle:
                handle.write('path: .\n')

            with self.assertRaises(TrainingCommandError):
                build_yolov8_train_command(
                    data_yaml=yaml_path,
                    output_dir=tmp_dir,
                    run_name='exp01',
                    model_size='nano',
                    epochs=0,
                    batch_size=4,
                    image_size=640,
                    patience=5)

            with self.assertRaises(TrainingCommandError):
                build_yolov8_train_command(
                    data_yaml=yaml_path,
                    output_dir=tmp_dir,
                    run_name='exp01',
                    model_size='nano',
                    epochs=10,
                    batch_size=4,
                    image_size=640,
                    patience=-1)

    def test_build_command_rejects_invalid_yaml_extension_and_run_name(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bad_yaml = os.path.join(tmp_dir, 'dataset.txt')
            with open(bad_yaml, 'w', encoding='utf-8') as handle:
                handle.write('path: .\n')

            with self.assertRaises(TrainingCommandError):
                build_yolov8_train_command(
                    data_yaml=bad_yaml,
                    output_dir=tmp_dir,
                    run_name='exp01',
                    model_size='nano',
                    epochs=10,
                    batch_size=4,
                    image_size=640,
                    patience=5)

            yaml_path = os.path.join(tmp_dir, 'dataset.yaml')
            with open(yaml_path, 'w', encoding='utf-8') as handle:
                handle.write('path: .\n')

            with self.assertRaises(TrainingCommandError):
                build_yolov8_train_command(
                    data_yaml=yaml_path,
                    output_dir=tmp_dir,
                    run_name='bad/name',
                    model_size='nano',
                    epochs=10,
                    batch_size=4,
                    image_size=640,
                    patience=5)

    def test_command_formatting_and_artifact_inference(self):
        command = ['yolo', 'task=detect', 'mode=train', 'name=exp 1']
        display = format_command_for_display(command)
        self.assertIn('task=detect', display)
        self.assertIn('name=', display)

        with tempfile.TemporaryDirectory() as tmp_dir:
            run_dir = os.path.join(tmp_dir, 'exp1')
            weights_dir = os.path.join(run_dir, 'weights')
            os.makedirs(weights_dir)
            best_path = os.path.join(weights_dir, 'best.pt')
            with open(best_path, 'wb') as handle:
                handle.write(b'weights')

            artifacts = infer_run_artifacts(tmp_dir, 'exp1')
            self.assertEqual(run_dir, artifacts['run_dir'])
            self.assertEqual(best_path, artifacts['best_pt'])

    def test_parse_yolov8_progress_epoch_line(self):
        parsed = parse_yolov8_progress_line(' 12/100 1.23G 0.92 0.61 1.05 24 640')
        self.assertIsNotNone(parsed)
        self.assertEqual(12, parsed.get('epoch'))
        self.assertEqual(100, parsed.get('total_epochs'))
        self.assertEqual(12, parsed.get('progress_percent'))

    def test_parse_yolov8_progress_metric_line(self):
        parsed = parse_yolov8_progress_line(
            'box_loss=0.9032 cls_loss=0.6511 dfl_loss=1.0210 precision=0.801 recall=0.755 mAP50=0.834 mAP50-95=0.521')
        self.assertIsNotNone(parsed)
        self.assertAlmostEqual(0.9032, parsed.get('box_loss'))
        self.assertAlmostEqual(0.6511, parsed.get('cls_loss'))
        self.assertAlmostEqual(1.0210, parsed.get('dfl_loss'))
        self.assertAlmostEqual(0.801, parsed.get('precision'))
        self.assertAlmostEqual(0.755, parsed.get('recall'))
        self.assertAlmostEqual(0.834, parsed.get('map50'))
        self.assertAlmostEqual(0.521, parsed.get('map50_95'))


if __name__ == '__main__':
    unittest.main()
