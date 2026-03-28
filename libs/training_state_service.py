import time

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


class TrainingStateService(object):
    METRIC_KEYS = ('box_loss', 'cls_loss', 'dfl_loss', 'precision', 'recall', 'map50', 'map50_95')

    def defaults(self, settings, current_path, last_exported_dataset_yaml):
        default_output_dir = settings.get(SETTING_TRAIN_LAST_OUTPUT_DIR, '') or current_path
        default_yaml = settings.get(SETTING_TRAIN_LAST_YAML_PATH, '')
        if not default_yaml and last_exported_dataset_yaml:
            default_yaml = last_exported_dataset_yaml
        return {
            'source_mode': settings.get(SETTING_TRAIN_LAST_SOURCE_MODE, 'last_export'),
            'last_export_yaml': last_exported_dataset_yaml,
            'yaml_path': default_yaml,
            'cli_executable': settings.get(SETTING_TRAIN_LAST_CLI, 'yolo'),
            'output_dir': default_output_dir,
            'run_name': settings.get(SETTING_TRAIN_LAST_RUN_NAME, 'train_exp'),
            'model_size': settings.get(SETTING_TRAIN_LAST_MODEL_SIZE, 'nano'),
            'epochs': settings.get(SETTING_TRAIN_LAST_EPOCHS, 100),
            'batch_size': settings.get(SETTING_TRAIN_LAST_BATCH_SIZE, 16),
            'image_size': settings.get(SETTING_TRAIN_LAST_IMAGE_SIZE, 640),
            'patience': settings.get(SETTING_TRAIN_LAST_PATIENCE, 50),
            'device': settings.get(SETTING_TRAIN_LAST_DEVICE, 'cpu'),
            'workers': settings.get(SETTING_TRAIN_LAST_WORKERS, 8),
            'extra_args': settings.get(SETTING_TRAIN_LAST_EXTRA_ARGS, ''),
        }

    def persist_defaults(self, settings, config):
        settings[SETTING_TRAIN_LAST_SOURCE_MODE] = config.get('source_mode', 'last_export')
        settings[SETTING_TRAIN_LAST_YAML_PATH] = config.get('yaml_path', '')
        settings[SETTING_TRAIN_LAST_CLI] = config.get('cli_executable', 'yolo')
        settings[SETTING_TRAIN_LAST_OUTPUT_DIR] = config.get('output_dir', '')
        settings[SETTING_TRAIN_LAST_RUN_NAME] = config.get('run_name', 'train_exp')
        settings[SETTING_TRAIN_LAST_MODEL_SIZE] = config.get('model_size', 'nano')
        settings[SETTING_TRAIN_LAST_EPOCHS] = config.get('epochs', 100)
        settings[SETTING_TRAIN_LAST_BATCH_SIZE] = config.get('batch_size', 16)
        settings[SETTING_TRAIN_LAST_IMAGE_SIZE] = config.get('image_size', 640)
        settings[SETTING_TRAIN_LAST_PATIENCE] = config.get('patience', 50)
        settings[SETTING_TRAIN_LAST_DEVICE] = config.get('device', 'cpu')
        settings[SETTING_TRAIN_LAST_WORKERS] = config.get('workers', 8)
        settings[SETTING_TRAIN_LAST_EXTRA_ARGS] = config.get('extra_args', '')

    def apply_progress_update(self, state, parsed, now=None):
        state.update(parsed or {})
        epoch = state.get('epoch')
        total = state.get('total_epochs')
        pct = state.get('progress_percent')

        epoch_text = None
        if epoch is not None and total is not None:
            epoch_text = 'Epoch: %d/%d (%d%%)' % (epoch, total, pct or 0)

        progress_value = None
        if pct is not None:
            progress_value = max(0, min(100, int(pct)))

        eta_text = None
        started_at = state.get('started_at')
        now_ts = time.time() if now is None else now
        if started_at and epoch is not None and total is not None and epoch > 0:
            elapsed_seconds = max(0.0, now_ts - started_at)
            estimated_total_seconds = elapsed_seconds * (float(total) / float(epoch))
            remaining_seconds = max(0, int(estimated_total_seconds - elapsed_seconds))
            eta_text = 'ETA: %s' % self.format_elapsed(remaining_seconds)

        metrics_text = self.metrics_text(state)
        return {
            'epoch_text': epoch_text,
            'progress_value': progress_value,
            'eta_text': eta_text,
            'metrics_text': metrics_text,
        }

    @classmethod
    def metrics_text(cls, state):
        metrics = []
        for key in cls.METRIC_KEYS:
            value = state.get(key)
            if value is not None:
                metrics.append('%s=%.4f' % (key, value))
        if not metrics:
            return None
        return 'Metrics: %s' % '  '.join(metrics)

    @staticmethod
    def format_elapsed(seconds):
        total = max(0, int(seconds))
        hours, rem = divmod(total, 3600)
        minutes, secs = divmod(rem, 60)
        if hours:
            return '%dh %02dm %02ds' % (hours, minutes, secs)
        if minutes:
            return '%dm %02ds' % (minutes, secs)
        return '%ds' % secs

    @classmethod
    def summary_text(cls, config, artifacts=None):
        if not config:
            return 'Run Summary: -'

        summary_lines = [
            'Run Summary:',
            'Model: YOLOv8 %s' % config.get('model_size', '-'),
            'Dataset: %s' % config.get('yaml_path', '-'),
            'Run: %s' % config.get('run_name', '-'),
            'Batch / Image Size: %s / %s' % (config.get('batch_size', '-'), config.get('image_size', '-')),
            'Output: %s' % config.get('output_dir', '-'),
        ]
        if artifacts and artifacts.get('best_pt'):
            summary_lines.append('Best Checkpoint: %s' % artifacts.get('best_pt'))
        return '\n'.join(summary_lines)

    def epoch_fraction(self, state):
        epoch = state.get('epoch')
        total = state.get('total_epochs')
        if epoch is None or total is None:
            return 'n/a'
        return '%d/%d' % (epoch, total)

    @classmethod
    def metrics_compact_text(cls, state):
        metrics = []
        for key in cls.METRIC_KEYS:
            value = state.get(key)
            if value is not None:
                metrics.append('%s=%.4f' % (key, value))
        if not metrics:
            return 'n/a'
        return ', '.join(metrics)