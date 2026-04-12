import os

try:
    from PyQt5.QtCore import QPointF
    from PyQt5.QtGui import QColor
except ImportError:
    from PyQt4.QtCore import QPointF
    from PyQt4.QtGui import QColor

from libs.labelFile import LabelFile, LabelFileError, LabelFileFormat
from libs.license_plate_io import LicensePlateIOError, ensure_txt_path, read_annotations, write_annotations
from libs.shape import Shape
from libs.ustr import ustr
from libs.utils import generate_color_by_text


class AnnotationWorkflowsMixin(object):
    """Annotation load/save workflow helpers extracted from MainWindow."""

    def load_labels(self, shapes):
        loaded_shapes = []
        for shape_data in shapes:
            if len(shape_data) >= 6:
                label, points, line_color, fill_color, difficult, is_segment = shape_data[:6]
            else:
                label, points, line_color, fill_color, difficult = shape_data
                is_segment = False
            shape = Shape(label=label)
            shape.is_segment = bool(is_segment)
            shape.max_points = None if shape.is_segment else 4
            for x, y in points:
                x, y, snapped = self.canvas.snap_point_to_canvas(x, y)
                if snapped:
                    self.set_dirty()
                shape.add_point(QPointF(x, y))
            shape.difficult = difficult
            shape.close()
            loaded_shapes.append(shape)

            if line_color:
                shape.line_color = QColor(*line_color)
            else:
                shape.line_color = generate_color_by_text(label)

            if fill_color:
                shape.fill_color = QColor(*fill_color)
            else:
                shape.fill_color = generate_color_by_text(label)

            self.add_label(shape)
        self.update_combo_box()
        self.canvas.load_shapes(loaded_shapes)

    def save_labels(self, annotation_file_path):
        annotation_file_path = ustr(annotation_file_path)
        if self.is_license_plate_mode():
            txt_path = ensure_txt_path(annotation_file_path)
            records = []
            for shape in self.canvas.shapes:
                bnd_box = LabelFile.convert_points_to_bnd_box([(p.x(), p.y()) for p in shape.points])
                records.append({
                    'plate': shape.label,
                    'xmin': bnd_box[0],
                    'ymin': bnd_box[1],
                    'xmax': bnd_box[2],
                    'ymax': bnd_box[3],
                })
            try:
                write_annotations(txt_path, records)
                print('Image:{0} -> Annotation:{1}'.format(self.file_path, txt_path))
                return True
            except LicensePlateIOError as e:
                self.error_message(u'Error saving label data', u'<b>%s</b>' % e)
                return False

        if self.label_file is None:
            self.label_file = LabelFile()
            self.label_file.verified = self.canvas.verified

        def format_shape(shape):
            return dict(
                label=shape.label,
                line_color=shape.line_color.getRgb(),
                fill_color=shape.fill_color.getRgb(),
                points=[(p.x(), p.y()) for p in shape.points],
                is_segment=bool(getattr(shape, 'is_segment', False)),
                difficult=shape.difficult,
            )

        shapes = [format_shape(shape) for shape in self.canvas.shapes]
        try:
            adapter = self.annotation_io.get_by_format(self.label_file_format)
            if adapter is not None:
                annotation_file_path = adapter.ensure_extension(annotation_file_path)
                adapter.save(
                    label_file=self.label_file,
                    annotation_file_path=annotation_file_path,
                    shapes=shapes,
                    file_path=self.file_path,
                    image_data=self.image_data,
                    label_hist=self.label_hist,
                    line_color=self.line_color.getRgb(),
                    fill_color=self.fill_color.getRgb(),
                )
            else:
                self.label_file.save(
                    annotation_file_path,
                    shapes,
                    self.file_path,
                    self.image_data,
                    self.line_color.getRgb(),
                    self.fill_color.getRgb(),
                )
            print('Image:{0} -> Annotation:{1}'.format(self.file_path, annotation_file_path))
            return True
        except LabelFileError as e:
            self.error_message(u'Error saving label data', u'<b>%s</b>' % e)
            return False

    def load_pascal_xml_by_filename(self, xml_path):
        if self.file_path is None:
            return
        if not xml_path or (not self._is_file(xml_path)):
            return

        adapter = self.annotation_io.get_by_format(LabelFileFormat.PASCAL_VOC)
        self.set_format(adapter.save_format)
        shapes, verified = adapter.load(xml_path, self.image, self.file_path)
        self.load_labels(shapes)
        self.canvas.verified = verified

    def load_yolo_txt_by_filename(self, txt_path):
        if self.file_path is None:
            return
        if not txt_path or (not self._is_file(txt_path)):
            return

        adapter = self.annotation_io.get_by_format(LabelFileFormat.YOLO)
        self.set_format(adapter.save_format)
        try:
            shapes, verified = adapter.load(txt_path, self.image, self.file_path)
        except Exception as e:
            self.error_message(
                u'Error loading label data',
                u'<b>%s</b><br/><br/>This txt does not look like YOLO format. '
                u'If this is license plate data, switch to License Plate mode and open again.' % e,
            )
            return
        self.load_labels(shapes)
        self.canvas.verified = verified

    def load_license_plate_txt_by_filename(self, txt_path):
        if self.file_path is None:
            return
        if not txt_path or (not self._is_file(txt_path)):
            return

        if self._file_looks_like_yolo_txt(txt_path):
            self.error_message(
                u'Error loading label data',
                u'This txt looks like YOLO annotation format. '
                u'License Plate mode expects rows like: <plate_text> xmin ymin xmax ymax',
            )
            return

        try:
            records = read_annotations(txt_path)
        except LicensePlateIOError as e:
            self.error_message(u'Error loading label data', u'<b>%s</b>' % e)
            return

        shapes = []
        for record in records:
            x_min = record['xmin']
            y_min = record['ymin']
            x_max = record['xmax']
            y_max = record['ymax']
            points = [(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)]
            shapes.append((record['plate'], points, None, None, False))

        self.load_labels(shapes)
        self.canvas.verified = False

    def load_create_ml_json_by_filename(self, json_path, file_path):
        if self.file_path is None:
            return
        if not json_path or (not self._is_file(json_path)):
            return

        adapter = self.annotation_io.get_by_format(LabelFileFormat.CREATE_ML)
        self.set_format(adapter.save_format)
        shapes, verified = adapter.load(json_path, self.image, file_path)
        self.load_labels(shapes)
        self.canvas.verified = verified

    @staticmethod
    def _is_file(path):
        return os.path.isfile(path)

    @staticmethod
    def _looks_like_yolo_line(raw_line):
        parts = (raw_line or '').strip().split()
        if len(parts) != 5:
            return False

        try:
            class_index = int(parts[0])
            x_center = float(parts[1])
            y_center = float(parts[2])
            width = float(parts[3])
            height = float(parts[4])
        except (TypeError, ValueError):
            return False

        if class_index < 0:
            return False

        # YOLO boxes are normalized to [0, 1].
        values = (x_center, y_center, width, height)
        return all(0.0 <= value <= 1.0 for value in values)

    def _file_looks_like_yolo_txt(self, txt_path):
        try:
            with open(txt_path, 'r', encoding='utf-8') as handle:
                for raw_line in handle:
                    stripped = raw_line.strip()
                    if not stripped:
                        continue
                    return self._looks_like_yolo_line(stripped)
        except OSError:
            return False
        return False
