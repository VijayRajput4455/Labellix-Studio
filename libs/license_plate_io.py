import os
import shutil

from libs.atomic_io import atomic_write_json, atomic_write_text


class LicensePlateIOError(Exception):
    pass


class LicensePlateDatasetSession(object):
    def __init__(self, source_dir=None):
        self.source_dir = source_dir

    @staticmethod
    def _unique_target_path(directory, filename):
        base, ext = os.path.splitext(filename)
        candidate = os.path.join(directory, filename)
        suffix = 1
        while os.path.exists(candidate):
            candidate = os.path.join(directory, '%s_%d%s' % (base, suffix, ext))
            suffix += 1
        return candidate

    def export_dataset(self, output_dir, image_paths, move_images=False, skip_unlabeled=True):
        if not self.source_dir or not os.path.isdir(self.source_dir):
            raise LicensePlateIOError('Invalid source directory for license plate export.')
        if not output_dir:
            raise LicensePlateIOError('Missing output directory for license plate export.')
        if not image_paths:
            raise LicensePlateIOError('No images were provided for export.')

        output_dir = os.path.abspath(output_dir)
        source_root = os.path.realpath(self.source_dir)
        output_root = os.path.realpath(output_dir)
        if source_root == output_root:
            raise LicensePlateIOError('Output directory must be different from source directory.')
        if os.path.exists(output_dir):
            raise LicensePlateIOError('Output directory already exists: %s' % output_dir)
        output_parent = os.path.dirname(output_dir) or '.'
        if not os.path.isdir(output_parent):
            raise LicensePlateIOError('Parent directory does not exist for output path: %s' % output_parent)
        if not os.access(output_parent, os.W_OK):
            raise LicensePlateIOError('Output parent directory is not writable: %s' % output_parent)

        labeled_pairs = []
        skipped_images = []
        for image_path in image_paths:
            if not image_path:
                raise LicensePlateIOError('Image path is empty.')
            image_abs = os.path.abspath(image_path)
            if not os.path.isfile(image_abs):
                raise LicensePlateIOError('Image file not found: %s' % image_abs)

            image_real = os.path.realpath(image_abs)
            if not image_real.startswith(source_root + os.path.sep) and image_real != source_root:
                raise LicensePlateIOError('Image path is outside source directory: %s' % image_abs)

            txt_path = ensure_txt_path(os.path.splitext(image_abs)[0])
            if os.path.isfile(txt_path):
                labeled_pairs.append((image_abs, txt_path))
            elif skip_unlabeled:
                skipped_images.append(image_abs)
            else:
                raise LicensePlateIOError('Missing license plate label txt for image: %s' % image_abs)

        if not labeled_pairs:
            raise LicensePlateIOError('No labeled images found to export.')

        images_dir = os.path.join(output_dir, 'images')
        labels_dir = os.path.join(output_dir, 'labels')
        os.makedirs(images_dir, exist_ok=True)
        os.makedirs(labels_dir, exist_ok=True)

        operation = shutil.move if move_images else shutil.copy2
        exported_count = 0
        for image_path, txt_path in labeled_pairs:
            image_name = os.path.basename(image_path)
            target_image_path = self._unique_target_path(images_dir, image_name)
            try:
                operation(image_path, target_image_path)
            except OSError as exc:
                raise LicensePlateIOError('Failed to export image %s -> %s: %s' % (image_path, target_image_path, exc))

            label_name = os.path.splitext(os.path.basename(target_image_path))[0] + '.txt'
            target_label_path = os.path.join(labels_dir, label_name)
            try:
                operation(txt_path, target_label_path)
            except OSError as exc:
                raise LicensePlateIOError('Failed to export label %s -> %s: %s' % (txt_path, target_label_path, exc))
            exported_count += 1

        report_path = os.path.join(output_dir, 'export_report.json')
        report_payload = {
            'source_dir': os.path.abspath(self.source_dir),
            'output_dir': output_dir,
            'images_dir': images_dir,
            'labels_dir': labels_dir,
            'exported_count': exported_count,
            'skipped_unlabeled': len(skipped_images),
            'skipped_images': skipped_images,
            'move_images': bool(move_images),
        }
        try:
            atomic_write_json(report_path, report_payload, encoding='utf-8', indent=2, sort_keys=True)
        except OSError as exc:
            raise LicensePlateIOError('Failed to write export report %s: %s' % (report_path, exc))

        return {
            'output_dir': output_dir,
            'images_dir': images_dir,
            'labels_dir': labels_dir,
            'report_path': report_path,
            'exported_count': exported_count,
            'skipped_unlabeled': len(skipped_images),
            'skipped_images': skipped_images,
            'move_images': bool(move_images),
        }


def ensure_txt_path(annotation_file_path):
    path = annotation_file_path or ''
    if path.lower().endswith('.txt'):
        return path
    return path + '.txt'


def _line_to_record(line):
    raw = (line or '').strip()
    if not raw:
        return None

    if '\t' in raw:
        parts = [part.strip() for part in raw.split('\t') if part.strip()]
    else:
        parts = raw.split()
    if len(parts) < 5:
        raise LicensePlateIOError('Malformed license plate annotation row: %s' % raw)

    plate_text = ' '.join(parts[:-4]).strip()
    if not plate_text:
        raise LicensePlateIOError('License plate text is missing in row: %s' % raw)

    try:
        x_min = int(float(parts[-4]))
        y_min = int(float(parts[-3]))
        x_max = int(float(parts[-2]))
        y_max = int(float(parts[-1]))
    except (TypeError, ValueError):
        raise LicensePlateIOError('Bounding box values must be numeric in row: %s' % raw)

    return {
        'plate': plate_text,
        'xmin': x_min,
        'ymin': y_min,
        'xmax': x_max,
        'ymax': y_max,
    }


def read_annotations(txt_path):
    if not txt_path or not os.path.isfile(txt_path):
        return []

    records = []
    try:
        with open(txt_path, 'r', encoding='utf-8') as handle:
            for line in handle:
                record = _line_to_record(line)
                if record is not None:
                    records.append(record)
    except OSError as exc:
        raise LicensePlateIOError('Failed to read license plate annotation file %s: %s' % (txt_path, exc))

    return records


def write_annotations(txt_path, records):
    lines = []
    for record in records:
        plate = str(record.get('plate', '')).strip()
        if not plate:
            raise LicensePlateIOError('License plate text cannot be empty.')

        for key in ('xmin', 'ymin', 'xmax', 'ymax'):
            if key not in record:
                raise LicensePlateIOError('Missing %s in license plate annotation record.' % key)

        try:
            x_min = int(float(record['xmin']))
            y_min = int(float(record['ymin']))
            x_max = int(float(record['xmax']))
            y_max = int(float(record['ymax']))
        except (TypeError, ValueError):
            raise LicensePlateIOError('Bounding box values must be numeric for plate %s.' % plate)

        lines.append('%s\t%d\t%d\t%d\t%d' % (plate, x_min, y_min, x_max, y_max))

    payload = '\n'.join(lines) + ('\n' if lines else '')
    try:
        atomic_write_text(txt_path, payload, encoding='utf-8')
    except OSError as exc:
        raise LicensePlateIOError('Failed to write license plate annotation file %s: %s' % (txt_path, exc))
