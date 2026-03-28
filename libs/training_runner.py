import os
import re
import shlex


class TrainingCommandError(Exception):
    pass


YOLOV8_MODEL_WEIGHTS = {
    'nano': 'yolov8n.pt',
    'small': 'yolov8s.pt',
    'medium': 'yolov8m.pt',
    'large': 'yolov8l.pt',
    'xlarge': 'yolov8x.pt',
}


def _require_positive_int(value, name):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise TrainingCommandError('%s must be an integer.' % name)
    if number <= 0:
        raise TrainingCommandError('%s must be greater than 0.' % name)
    return number


def _optional_nonnegative_int(value, name):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise TrainingCommandError('%s must be an integer.' % name)
    if number < 0:
        raise TrainingCommandError('%s must be 0 or greater.' % name)
    return number


def build_yolov8_train_command(
        data_yaml,
        output_dir,
        run_name,
        model_size,
        epochs,
        batch_size,
        image_size,
        patience,
        device='cpu',
        workers=8,
        cli_executable='yolo',
        extra_args=''):
    if not data_yaml:
        raise TrainingCommandError('Dataset yaml path is required.')

    data_yaml = os.path.abspath(data_yaml)
    if not os.path.isfile(data_yaml):
        raise TrainingCommandError('Dataset yaml file does not exist: %s' % data_yaml)
    if not data_yaml.lower().endswith(('.yaml', '.yml')):
        raise TrainingCommandError('Dataset config must be a .yaml or .yml file: %s' % data_yaml)

    if not output_dir:
        raise TrainingCommandError('Output directory is required.')
    output_dir = os.path.abspath(output_dir)
    if os.path.exists(output_dir) and not os.path.isdir(output_dir):
        raise TrainingCommandError('Output path exists and is not a directory: %s' % output_dir)
    output_parent = os.path.dirname(output_dir) or '.'
    if not os.path.isdir(output_parent):
        raise TrainingCommandError('Parent directory does not exist for output path: %s' % output_parent)
    if not os.access(output_parent, os.W_OK):
        raise TrainingCommandError('Output parent directory is not writable: %s' % output_parent)

    run_name = (run_name or '').strip()
    if not run_name:
        raise TrainingCommandError('Run name is required.')
    if '/' in run_name or '\\' in run_name:
        raise TrainingCommandError('Run name cannot contain path separators.')
    if run_name in ('.', '..'):
        raise TrainingCommandError('Run name cannot be . or ..')

    if model_size not in YOLOV8_MODEL_WEIGHTS:
        raise TrainingCommandError('Unsupported YOLOv8 model size: %s' % model_size)

    epochs = _require_positive_int(epochs, 'Epochs')
    batch_size = _require_positive_int(batch_size, 'Batch size')
    image_size = _require_positive_int(image_size, 'Image size')
    patience = _optional_nonnegative_int(patience, 'Patience')
    workers = _optional_nonnegative_int(workers, 'Workers')

    cli_executable = (cli_executable or 'yolo').strip()
    device = (device or 'cpu').strip()
    if not device:
        device = 'cpu'

    command = [
        cli_executable,
        'task=detect',
        'mode=train',
        'model=%s' % YOLOV8_MODEL_WEIGHTS[model_size],
        'data=%s' % data_yaml,
        'project=%s' % output_dir,
        'name=%s' % run_name,
        'epochs=%d' % epochs,
        'batch=%d' % batch_size,
        'imgsz=%d' % image_size,
        'patience=%d' % patience,
        'device=%s' % device,
        'workers=%d' % workers,
    ]

    if extra_args:
        try:
            command.extend(shlex.split(extra_args))
        except ValueError as exc:
            raise TrainingCommandError('Could not parse extra args: %s' % exc)

    return command


def format_command_for_display(command_parts):
    return ' '.join([shlex.quote(part) for part in command_parts])


def infer_run_artifacts(output_dir, run_name):
    run_dir = os.path.join(os.path.abspath(output_dir), run_name)
    best_pt = os.path.join(run_dir, 'weights', 'best.pt')
    if not os.path.isfile(best_pt):
        best_pt = ''
    return {
        'run_dir': run_dir,
        'best_pt': best_pt,
    }


_EPOCH_PATTERN = re.compile(r'\b(?P<epoch>\d+)\s*/\s*(?P<total>\d+)\b')
_KV_FLOAT_PATTERN = {
    'box_loss': re.compile(r'\bbox_loss\s*[:=]\s*(?P<value>\d+(?:\.\d+)?)\b', re.IGNORECASE),
    'cls_loss': re.compile(r'\bcls_loss\s*[:=]\s*(?P<value>\d+(?:\.\d+)?)\b', re.IGNORECASE),
    'dfl_loss': re.compile(r'\bdfl_loss\s*[:=]\s*(?P<value>\d+(?:\.\d+)?)\b', re.IGNORECASE),
    'precision': re.compile(r'\bprecision\s*[:=]\s*(?P<value>\d+(?:\.\d+)?)\b', re.IGNORECASE),
    'recall': re.compile(r'\brecall\s*[:=]\s*(?P<value>\d+(?:\.\d+)?)\b', re.IGNORECASE),
    'map50': re.compile(r'\bm(?:AP|ap)50\s*[:=]\s*(?P<value>\d+(?:\.\d+)?)\b', re.IGNORECASE),
    'map50_95': re.compile(r'\bm(?:AP|ap)50-95\s*[:=]\s*(?P<value>\d+(?:\.\d+)?)\b', re.IGNORECASE),
}


def parse_yolov8_progress_line(line):
    text = (line or '').strip()
    if not text:
        return None

    parsed = {}

    epoch_match = _EPOCH_PATTERN.search(text)
    if epoch_match:
        epoch = int(epoch_match.group('epoch'))
        total = int(epoch_match.group('total'))
        if total > 0:
            parsed['epoch'] = epoch
            parsed['total_epochs'] = total
            parsed['progress_percent'] = int((float(epoch) / float(total)) * 100)

    for key, pattern in _KV_FLOAT_PATTERN.items():
        match = pattern.search(text)
        if match:
            parsed[key] = float(match.group('value'))

    return parsed or None
