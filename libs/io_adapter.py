#!/usr/bin/env python
# -*- coding: utf-8 -*-

from libs.constants import FORMAT_CREATEML, FORMAT_PASCALVOC, FORMAT_YOLO
from libs.create_ml_io import CreateMLReader, JSON_EXT
from libs.labelFile import LabelFileFormat
from libs.pascal_voc_io import PascalVocReader, XML_EXT
from libs.yolo_io import YoloReader, TXT_EXT


class AnnotationIOAdapter(object):

    def __init__(self, label_file_format, extension, save_format):
        self.label_file_format = label_file_format
        self.extension = extension
        self.save_format = save_format

    def ensure_extension(self, annotation_file_path):
        if annotation_file_path.lower().endswith(self.extension):
            return annotation_file_path
        return annotation_file_path + self.extension

    def load(self, annotation_path, image, file_path):
        raise NotImplementedError()

    def save(self, label_file, annotation_file_path, shapes, file_path, image_data, label_hist, line_color, fill_color):
        raise NotImplementedError()


class PascalVOCAdapter(AnnotationIOAdapter):

    def __init__(self):
        super(PascalVOCAdapter, self).__init__(LabelFileFormat.PASCAL_VOC, XML_EXT, FORMAT_PASCALVOC)

    def load(self, annotation_path, image, file_path):
        reader = PascalVocReader(annotation_path)
        return reader.get_shapes(), reader.verified

    def save(self, label_file, annotation_file_path, shapes, file_path, image_data, label_hist, line_color, fill_color):
        label_file.save_pascal_voc_format(annotation_file_path, shapes, file_path, image_data, line_color, fill_color)


class YOLOAdapter(AnnotationIOAdapter):

    def __init__(self):
        super(YOLOAdapter, self).__init__(LabelFileFormat.YOLO, TXT_EXT, FORMAT_YOLO)

    def load(self, annotation_path, image, file_path):
        reader = YoloReader(annotation_path, image)
        return reader.get_shapes(), reader.verified

    def save(self, label_file, annotation_file_path, shapes, file_path, image_data, label_hist, line_color, fill_color):
        label_file.save_yolo_format(annotation_file_path, shapes, file_path, image_data, label_hist, line_color, fill_color)


class CreateMLAdapter(AnnotationIOAdapter):

    def __init__(self):
        super(CreateMLAdapter, self).__init__(LabelFileFormat.CREATE_ML, JSON_EXT, FORMAT_CREATEML)

    def load(self, annotation_path, image, file_path):
        reader = CreateMLReader(annotation_path, file_path)
        return reader.get_shapes(), reader.verified

    def save(self, label_file, annotation_file_path, shapes, file_path, image_data, label_hist, line_color, fill_color):
        label_file.save_create_ml_format(annotation_file_path, shapes, file_path, image_data, label_hist, line_color, fill_color)


class AnnotationIORegistry(object):

    def __init__(self):
        self._by_format = {
            LabelFileFormat.PASCAL_VOC: PascalVOCAdapter(),
            LabelFileFormat.YOLO: YOLOAdapter(),
            LabelFileFormat.CREATE_ML: CreateMLAdapter(),
        }

    def get_by_format(self, label_file_format):
        return self._by_format.get(label_file_format)
