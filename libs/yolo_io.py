#!/usr/bin/env python
# -*- coding: utf8 -*-
import codecs
import hashlib
import json
import logging
import os
import random
import shutil

from libs.constants import DEFAULT_ENCODING
from libs.atomic_io import atomic_write_json, atomic_write_text
from libs.io_validation import (
    ensure_directory,
    ensure_distinct_directories,
    ensure_new_output_directory,
    ensure_path_within_root,
    ensure_required_path,
)

TXT_EXT = '.txt'
ENCODE_METHOD = DEFAULT_ENCODING
LOGGER = logging.getLogger(__name__)

class YOLOWriter:

    def __init__(self, folder_name, filename, img_size, database_src='Unknown', local_img_path=None):
        self.folder_name = folder_name
        self.filename = filename
        self.database_src = database_src
        self.img_size = img_size
        self.box_list = []
        self.local_img_path = local_img_path
        self.verified = False

    def add_bnd_box(self, x_min, y_min, x_max, y_max, name, difficult):
        bnd_box = {'xmin': x_min, 'ymin': y_min, 'xmax': x_max, 'ymax': y_max}
        bnd_box['name'] = name
        bnd_box['difficult'] = difficult
        self.box_list.append(bnd_box)

    def bnd_box_to_yolo_line(self, box, class_list=[]):
        x_min = box['xmin']
        x_max = box['xmax']
        y_min = box['ymin']
        y_max = box['ymax']

        x_center = float((x_min + x_max)) / 2 / self.img_size[1]
        y_center = float((y_min + y_max)) / 2 / self.img_size[0]

        w = float((x_max - x_min)) / self.img_size[1]
        h = float((y_max - y_min)) / self.img_size[0]

        # PR387
        box_name = box['name']
        if box_name not in class_list:
            class_list.append(box_name)

        class_index = class_list.index(box_name)

        return class_index, x_center, y_center, w, h

    def save(self, class_list=[], target_file=None):
        if target_file is None:
            labels_file = self.filename + TXT_EXT
            classes_file = os.path.join(os.path.dirname(os.path.abspath(self.filename)), 'classes.txt')
        else:
            labels_file = target_file
            classes_file = os.path.join(os.path.dirname(os.path.abspath(target_file)), 'classes.txt')

        label_lines = []
        for box in self.box_list:
            class_index, x_center, y_center, w, h = self.bnd_box_to_yolo_line(box, class_list)
            label_lines.append('%d %.6f %.6f %.6f %.6f' % (class_index, x_center, y_center, w, h))

        class_lines = [str(c) for c in class_list]
        atomic_write_text(labels_file, ('\n'.join(label_lines) + ('\n' if label_lines else '')), encoding=ENCODE_METHOD)
        atomic_write_text(classes_file, ('\n'.join(class_lines) + ('\n' if class_lines else '')), encoding=ENCODE_METHOD)



class YoloReader:

    def __init__(self, file_path, image, class_list_path=None):
        # shapes type:
        # [labbel, [(x1,y1), (x2,y2), (x3,y3), (x4,y4)], color, color, difficult]
        self.shapes = []
        self.file_path = file_path

        if class_list_path is None:
            dir_path = os.path.dirname(os.path.realpath(self.file_path))
            self.class_list_path = os.path.join(dir_path, "classes.txt")
        else:
            self.class_list_path = class_list_path

        # print (file_path, self.class_list_path)

        with open(self.class_list_path, 'r', encoding=ENCODE_METHOD) as classes_file:
            self.classes = classes_file.read().strip('\n').split('\n')

        # print (self.classes)

        img_size = [image.height(), image.width(),
                    1 if image.isGrayscale() else 3]

        self.img_size = img_size

        self.verified = False
        # try:
        self.parse_yolo_format()
        # except:
        #     pass

    def get_shapes(self):
        return self.shapes

    def add_shape(self, label, x_min, y_min, x_max, y_max, difficult):

        points = [(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)]
        self.shapes.append((label, points, None, None, difficult))

    def yolo_line_to_shape(self, class_index, x_center, y_center, w, h):
        label = self.classes[int(class_index)]

        x_min = max(float(x_center) - float(w) / 2, 0)
        x_max = min(float(x_center) + float(w) / 2, 1)
        y_min = max(float(y_center) - float(h) / 2, 0)
        y_max = min(float(y_center) + float(h) / 2, 1)

        x_min = round(self.img_size[1] * x_min)
        x_max = round(self.img_size[1] * x_max)
        y_min = round(self.img_size[0] * y_min)
        y_max = round(self.img_size[0] * y_max)

        return label, x_min, y_min, x_max, y_max

    def parse_yolo_format(self):
        with open(self.file_path, 'r', encoding=ENCODE_METHOD) as bnd_box_file:
            for bnd_box in bnd_box_file:
                parts = bnd_box.strip().split()
                if len(parts) != 5:
                    continue

                class_index, x_center, y_center, w, h = parts
                label, x_min, y_min, x_max, y_max = self.yolo_line_to_shape(class_index, x_center, y_center, w, h)

                # Caveat: difficult flag is discarded when saved as yolo format.
                self.add_shape(label, x_min, y_min, x_max, y_max, False)


class YOLODatasetExportError(Exception):
    pass


class YOLODatasetSession(object):
    def __init__(self, source_dir=None, seed=42):
        self.source_dir = source_dir
        self.seed = seed

    def _classes_path(self):
        return os.path.join(self.source_dir, 'classes.txt')

    def _load_classes(self):
        classes_path = self._classes_path()
        if not os.path.exists(classes_path):
            raise YOLODatasetExportError('classes.txt not found in source directory: %s' % self.source_dir)

        with open(classes_path, 'r', encoding=ENCODE_METHOD) as classes_file:
            classes = [line.strip() for line in classes_file if line.strip()]

        if not classes:
            raise YOLODatasetExportError('classes.txt is empty.')
        return classes

    @staticmethod
    def _safe_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _validate_percentages(train_percent, test_percent, valid_percent):
        values = [train_percent, test_percent, valid_percent]
        if any(value < 0 or value > 100 for value in values):
            raise YOLODatasetExportError('Split ratios must be between 0 and 100.')
        if sum(values) != 100:
            raise YOLODatasetExportError('Split ratios must sum to 100.')

    @staticmethod
    def _allocate_counts(total, train_percent, test_percent, valid_percent):
        if total <= 0:
            return {'train': 0, 'test': 0, 'valid': 0}

        targets = {
            'train': total * train_percent / 100.0,
            'test': total * test_percent / 100.0,
            'valid': total * valid_percent / 100.0,
        }
        counts = {split: int(targets[split]) for split in targets}
        remainder = total - sum(counts.values())

        if remainder > 0:
            by_fraction = sorted(
                ((targets[split] - counts[split], split) for split in counts),
                reverse=True,
            )
            for _fraction, split in by_fraction[:remainder]:
                counts[split] += 1

        return counts

    @staticmethod
    def _unique_target_path(directory, filename):
        base, ext = os.path.splitext(filename)
        candidate = os.path.join(directory, filename)
        suffix = 1
        while os.path.exists(candidate):
            candidate = os.path.join(directory, '%s_%d%s' % (base, suffix, ext))
            suffix += 1
        return candidate

    def _labeled_pairs(self, image_paths, skip_unlabeled=True):
        labeled_pairs = []
        skipped_images = []

        for image_path in image_paths:
            label_path = os.path.splitext(image_path)[0] + TXT_EXT
            if os.path.exists(label_path):
                labeled_pairs.append((image_path, label_path))
            elif skip_unlabeled:
                skipped_images.append(image_path)
            else:
                raise YOLODatasetExportError('Missing YOLO label txt for image: %s' % image_path)

        return labeled_pairs, skipped_images

    @staticmethod
    def _image_fingerprint(image_path):
        hasher = hashlib.sha1()
        size = os.path.getsize(image_path)
        with open(image_path, 'rb') as handle:
            sample = handle.read(256 * 1024)
        hasher.update(sample)
        hasher.update(str(size).encode('ascii'))
        return hasher.hexdigest()

    def _scan_quality(self, labeled_pairs, classes):
        class_count = len(classes)
        class_histogram = {name: 0 for name in classes}
        empty_label_images = []
        invalid_class_images = []
        malformed_label_images = []
        duplicate_groups = {}

        for image_path, label_path in labeled_pairs:
            try:
                fingerprint = self._image_fingerprint(image_path)
                duplicate_groups.setdefault(fingerprint, []).append(image_path)
            except OSError:
                pass

            with open(label_path, 'r', encoding=ENCODE_METHOD) as label_file:
                lines = [line.strip() for line in label_file if line.strip()]

            if not lines:
                empty_label_images.append(image_path)
                continue

            has_invalid_class = False
            has_malformed = False
            for line in lines:
                parts = line.split()
                if len(parts) < 1:
                    has_malformed = True
                    continue
                class_index = self._safe_int(parts[0])
                if class_index is None:
                    has_malformed = True
                    continue
                if class_index < 0 or class_index >= class_count:
                    has_invalid_class = True
                else:
                    class_histogram[classes[class_index]] += 1

            if has_invalid_class:
                invalid_class_images.append(image_path)
            if has_malformed:
                malformed_label_images.append(image_path)

        duplicate_sets = [paths for paths in duplicate_groups.values() if len(paths) > 1]
        return {
            'class_histogram': class_histogram,
            'empty_label_images': empty_label_images,
            'invalid_class_images': invalid_class_images,
            'malformed_label_images': malformed_label_images,
            'duplicate_groups': duplicate_sets,
        }

    def _assign_split_ranges(self, labeled_pairs, counts, stratified=False, classes=None):
        if not stratified:
            return {
                'train': labeled_pairs[0:counts['train']],
                'test': labeled_pairs[counts['train']:counts['train'] + counts['test']],
                'valid': labeled_pairs[counts['train'] + counts['test']:],
            }

        split_data = {'train': [], 'test': [], 'valid': []}
        randomizer = random.Random(self.seed)
        by_class = {}

        for image_path, label_path in labeled_pairs:
            primary = self._primary_class_for_label(label_path, classes)
            by_class.setdefault(primary, []).append((image_path, label_path))

        for class_name in by_class:
            randomizer.shuffle(by_class[class_name])

        class_order = list(by_class.keys())
        randomizer.shuffle(class_order)

        remaining = dict(counts)
        for class_name in class_order:
            bucket = by_class[class_name]
            while bucket:
                target_splits = sorted(remaining.keys(), key=lambda key: remaining[key], reverse=True)
                target = target_splits[0]
                if remaining[target] <= 0:
                    break
                split_data[target].append(bucket.pop())
                remaining[target] -= 1

            for item in bucket:
                target_splits = sorted(remaining.keys(), key=lambda key: remaining[key], reverse=True)
                split_data[target_splits[0]].append(item)

        # Fill any remaining count gaps from existing pool order.
        all_items = split_data['train'] + split_data['test'] + split_data['valid']
        split_data = {'train': [], 'test': [], 'valid': []}
        split_data['train'] = all_items[0:counts['train']]
        split_data['test'] = all_items[counts['train']:counts['train'] + counts['test']]
        split_data['valid'] = all_items[counts['train'] + counts['test']:]
        return split_data

    def _ordered_pairs_for_split(self, labeled_pairs, shuffle=True):
        ordered = list(labeled_pairs)
        if shuffle:
            randomizer = random.Random(self.seed)
            randomizer.shuffle(ordered)
        return ordered

    @staticmethod
    def _primary_class_for_label(label_path, classes):
        if not classes:
            return '__none__'
        with open(label_path, 'r', encoding=ENCODE_METHOD) as label_file:
            lines = [line.strip() for line in label_file if line.strip()]
        if not lines:
            return '__empty__'

        counts = {}
        for line in lines:
            parts = line.split()
            if not parts:
                continue
            try:
                class_index = int(parts[0])
            except ValueError:
                continue
            if 0 <= class_index < len(classes):
                class_name = classes[class_index]
                counts[class_name] = counts.get(class_name, 0) + 1
        if not counts:
            return '__unknown__'
        return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]

    def preview_split(self, image_paths, train_percent=80, test_percent=10, valid_percent=10,
                      skip_unlabeled=True, stratified=False, shuffle=True):
        self._validate_percentages(train_percent, test_percent, valid_percent)
        classes = self._load_classes()
        labeled_pairs, skipped_images = self._labeled_pairs(image_paths, skip_unlabeled=skip_unlabeled)
        ordered_pairs = self._ordered_pairs_for_split(labeled_pairs, shuffle=shuffle)
        counts = self._allocate_counts(len(labeled_pairs), train_percent, test_percent, valid_percent)
        quality = self._scan_quality(labeled_pairs, classes)
        split_assignment = self._assign_split_ranges(ordered_pairs, counts, stratified=stratified, classes=classes)

        return {
            'classes': classes,
            'total_labeled': len(labeled_pairs),
            'skipped_unlabeled': len(skipped_images),
            'skipped_images': skipped_images,
            'counts': counts,
            'quality': quality,
            'split_assignment': split_assignment,
            'stratified': stratified,
            'shuffle': bool(shuffle),
        }

    @staticmethod
    def _create_split_dirs(output_dir):
        split_dirs = {}
        for split in ('train', 'test', 'valid'):
            image_dir = os.path.join(output_dir, split, 'images')
            label_dir = os.path.join(output_dir, split, 'labels')
            os.makedirs(image_dir, exist_ok=True)
            os.makedirs(label_dir, exist_ok=True)
            split_dirs[split] = {'images': image_dir, 'labels': label_dir}
        return split_dirs

    @staticmethod
    def _write_dataset_yaml(output_dir, classes):
        yaml_path = os.path.join(output_dir, 'dataset.yaml')
        names = ', '.join("'%s'" % name.replace("'", "\\'") for name in classes)
        content = [
            'path: .',
            'train: train/images',
            'val: valid/images',
            'test: test/images',
            'nc: %d' % len(classes),
            'names: [%s]' % names,
            '',
        ]
        try:
            atomic_write_text(yaml_path, '\n'.join(content), encoding=ENCODE_METHOD)
        except OSError as exc:
            LOGGER.exception('Failed to write YOLO dataset yaml to %s', yaml_path)
            raise YOLODatasetExportError('Failed to write dataset yaml %s: %s' % (yaml_path, exc))
        return yaml_path

    @staticmethod
    def _write_stats_report(output_dir, stats_payload):
        stats_path = os.path.join(output_dir, 'dataset_stats.json')
        try:
            atomic_write_json(stats_path, stats_payload, encoding=ENCODE_METHOD, indent=2, sort_keys=True)
        except OSError as exc:
            LOGGER.exception('Failed to write YOLO dataset stats to %s', stats_path)
            raise YOLODatasetExportError('Failed to write dataset stats %s: %s' % (stats_path, exc))
        return stats_path

    def export_dataset(self, output_dir, image_paths, train_percent=80, test_percent=10, valid_percent=10,
                       copy_images=True, skip_unlabeled=True, write_yaml=True, stratified=False,
                       shuffle=True,
                       write_stats=True):
        ensure_required_path(
            self.source_dir,
            YOLODatasetExportError,
            'Invalid source directory for YOLO export.',
        )
        ensure_directory(
            self.source_dir,
            YOLODatasetExportError,
            'Invalid source directory for YOLO export.',
        )
        ensure_required_path(
            output_dir,
            YOLODatasetExportError,
            'Missing output directory for YOLO export.',
        )
        output_dir = os.path.abspath(output_dir)
        source_root, _ = ensure_distinct_directories(
            self.source_dir,
            output_dir,
            YOLODatasetExportError,
            'Output directory must be different from source directory.',
        )
        output_parent = os.path.dirname(output_dir) or '.'
        ensure_new_output_directory(
            output_dir,
            YOLODatasetExportError,
            'Output directory already exists: %s' % output_dir,
            'Parent directory does not exist for output path: %s' % output_parent,
            'Output parent directory is not writable: %s' % output_parent,
        )

        if not image_paths:
            raise YOLODatasetExportError('No images were provided for export.')
        for image_path in image_paths:
            if not image_path:
                raise YOLODatasetExportError('Image path is empty.')
            image_abs = os.path.abspath(image_path)
            if not os.path.isfile(image_abs):
                raise YOLODatasetExportError('Image file not found: %s' % image_abs)
            ensure_path_within_root(
                image_abs,
                source_root,
                YOLODatasetExportError,
                'Image path is outside source directory: %s' % image_abs,
            )

        preview = self.preview_split(
            image_paths=image_paths,
            train_percent=train_percent,
            test_percent=test_percent,
            valid_percent=valid_percent,
            skip_unlabeled=skip_unlabeled,
            stratified=stratified,
            shuffle=shuffle,
        )
        classes = preview['classes']
        labeled_pairs, skipped_images = self._labeled_pairs(image_paths, skip_unlabeled=skip_unlabeled)
        if not labeled_pairs:
            raise YOLODatasetExportError('No labeled images found to export.')

        quality = preview.get('quality', {})
        if quality.get('invalid_class_images'):
            raise YOLODatasetExportError(
                'Class consistency check failed: %d files contain class index outside classes.txt.'
                % len(quality.get('invalid_class_images', []))
            )

        split_assignment = preview.get('split_assignment', {})

        split_dirs = self._create_split_dirs(output_dir)
        operation = shutil.copy2 if copy_images else shutil.move
        exported = {'train': 0, 'test': 0, 'valid': 0}

        for split in ('train', 'test', 'valid'):
            for image_path, label_path in split_assignment[split]:
                image_name = os.path.basename(image_path)
                target_image_path = self._unique_target_path(split_dirs[split]['images'], image_name)
                try:
                    operation(image_path, target_image_path)
                except OSError as exc:
                    LOGGER.exception('Failed to export image %s to %s', image_path, target_image_path)
                    raise YOLODatasetExportError('Failed to export image %s -> %s: %s' % (image_path, target_image_path, exc))

                label_name = os.path.splitext(os.path.basename(target_image_path))[0] + TXT_EXT
                target_label_path = os.path.join(split_dirs[split]['labels'], label_name)
                try:
                    operation(label_path, target_label_path)
                except OSError as exc:
                    LOGGER.exception('Failed to export label %s to %s', label_path, target_label_path)
                    raise YOLODatasetExportError('Failed to export label %s -> %s: %s' % (label_path, target_label_path, exc))
                exported[split] += 1

        yaml_path = None
        if write_yaml:
            yaml_path = self._write_dataset_yaml(output_dir, classes)

        stats_path = None
        if write_stats:
            stats_path = self._write_stats_report(output_dir, {
                'total_labeled': len(labeled_pairs),
                'skipped_unlabeled': len(skipped_images),
                'skipped_images': skipped_images,
                'split_distribution': exported,
                'class_histogram': quality.get('class_histogram', {}),
                'empty_label_images': quality.get('empty_label_images', []),
                'invalid_class_images': quality.get('invalid_class_images', []),
                'malformed_label_images': quality.get('malformed_label_images', []),
                'duplicate_groups': quality.get('duplicate_groups', []),
                'stratified': stratified,
                'shuffle': bool(shuffle),
                'seed': self.seed,
            })

        return {
            'output_dir': output_dir,
            'classes': classes,
            'yaml_path': yaml_path,
            'stats_path': stats_path,
            'total_labeled': len(labeled_pairs),
            'skipped_unlabeled': len(skipped_images),
            'skipped_images': skipped_images,
            'exported': exported,
            'quality': quality,
            'stratified': stratified,
            'shuffle': bool(shuffle),
        }
