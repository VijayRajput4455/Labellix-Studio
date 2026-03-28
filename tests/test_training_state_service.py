import unittest

from libs.constants import (
    SETTING_TRAIN_LAST_BATCH_SIZE,
    SETTING_TRAIN_LAST_CLI,
    SETTING_TRAIN_LAST_DEVICE,
    SETTING_TRAIN_LAST_EPOCHS,
    SETTING_TRAIN_LAST_EXTRA_ARGS,
    SETTING_TRAIN_LAST_IMAGE_SIZE,
    SETTING_TRAIN_LAST_MODEL_SIZE,
    SETTING_TRAIN_LAST_OUTPUT_DIR,
    SETTING_TRAIN_LAST_PATIENCE,
    SETTING_TRAIN_LAST_RUN_NAME,
    SETTING_TRAIN_LAST_SOURCE_MODE,
    SETTING_TRAIN_LAST_WORKERS,
    SETTING_TRAIN_LAST_YAML_PATH,
)
from libs.training_state_service import TrainingStateService


class TestTrainingStateService(unittest.TestCase):

    def test_defaults_prefers_last_export_yaml_when_missing_saved_yaml(self):
        settings = {
            SETTING_TRAIN_LAST_OUTPUT_DIR: '',
            SETTING_TRAIN_LAST_YAML_PATH: '',
        }
        service = TrainingStateService()

        defaults = service.defaults(
            settings=settings,
            current_path='/tmp/work',
            last_exported_dataset_yaml='/tmp/work/dataset.yaml',
        )

        self.assertEqual('/tmp/work', defaults['output_dir'])
        self.assertEqual('/tmp/work/dataset.yaml', defaults['yaml_path'])
        self.assertEqual('last_export', defaults['source_mode'])
        self.assertEqual('yolo', defaults['cli_executable'])

    def test_persist_defaults_writes_expected_keys(self):
        settings = {}
        config = {
            'source_mode': 'existing_yaml',
            'yaml_path': '/tmp/dataset.yaml',
            'cli_executable': 'python -m ultralytics',
            'output_dir': '/tmp/runs',
            'run_name': 'exp42',
            'model_size': 'small',
            'epochs': 50,
            'batch_size': 8,
            'image_size': 512,
            'patience': 20,
            'device': '0',
            'workers': 4,
            'extra_args': '--cache',
        }
        service = TrainingStateService()

        service.persist_defaults(settings, config)

        self.assertEqual('existing_yaml', settings[SETTING_TRAIN_LAST_SOURCE_MODE])
        self.assertEqual('/tmp/dataset.yaml', settings[SETTING_TRAIN_LAST_YAML_PATH])
        self.assertEqual('python -m ultralytics', settings[SETTING_TRAIN_LAST_CLI])
        self.assertEqual('/tmp/runs', settings[SETTING_TRAIN_LAST_OUTPUT_DIR])
        self.assertEqual('exp42', settings[SETTING_TRAIN_LAST_RUN_NAME])
        self.assertEqual('small', settings[SETTING_TRAIN_LAST_MODEL_SIZE])
        self.assertEqual(50, settings[SETTING_TRAIN_LAST_EPOCHS])
        self.assertEqual(8, settings[SETTING_TRAIN_LAST_BATCH_SIZE])
        self.assertEqual(512, settings[SETTING_TRAIN_LAST_IMAGE_SIZE])
        self.assertEqual(20, settings[SETTING_TRAIN_LAST_PATIENCE])
        self.assertEqual('0', settings[SETTING_TRAIN_LAST_DEVICE])
        self.assertEqual(4, settings[SETTING_TRAIN_LAST_WORKERS])
        self.assertEqual('--cache', settings[SETTING_TRAIN_LAST_EXTRA_ARGS])

    def test_apply_progress_update_computes_ui_values(self):
        service = TrainingStateService()
        state = {'started_at': 10.0}
        parsed = {
            'epoch': 2,
            'total_epochs': 4,
            'progress_percent': 50,
            'precision': 0.75,
            'recall': 0.65,
        }

        ui_state = service.apply_progress_update(state, parsed, now=30.0)

        self.assertEqual('Epoch: 2/4 (50%)', ui_state['epoch_text'])
        self.assertEqual(50, ui_state['progress_value'])
        self.assertEqual('ETA: 20s', ui_state['eta_text'])
        self.assertIn('precision=0.7500', ui_state['metrics_text'])
        self.assertIn('recall=0.6500', ui_state['metrics_text'])

    def test_summary_and_compact_metrics_text(self):
        service = TrainingStateService()
        summary = service.summary_text(
            config={
                'model_size': 'nano',
                'yaml_path': '/tmp/dataset.yaml',
                'run_name': 'exp',
                'batch_size': 16,
                'image_size': 640,
                'output_dir': '/tmp/runs',
            },
            artifacts={'best_pt': '/tmp/runs/exp/weights/best.pt'},
        )
        self.assertIn('Model: YOLOv8 nano', summary)
        self.assertIn('Best Checkpoint: /tmp/runs/exp/weights/best.pt', summary)

        state = {'epoch': 3, 'total_epochs': 5, 'map50': 0.42}
        self.assertEqual('3/5', service.epoch_fraction(state))
        self.assertEqual('map50=0.4200', service.metrics_compact_text(state))

    def test_format_elapsed_variants(self):
        service = TrainingStateService()
        self.assertEqual('7s', service.format_elapsed(7))
        self.assertEqual('1m 05s', service.format_elapsed(65))
        self.assertEqual('1h 01m 01s', service.format_elapsed(3661))


if __name__ == '__main__':
    unittest.main()
