#!/usr/bin/env python
# -*- coding: utf-8 -*-


class ApplicationState(object):
    """Central runtime state container for MainWindow.

    Keeps mutable application/session fields in one place so UI controllers
    and services can consume a shared source of truth.
    """

    def __init__(self, default_mode='detection'):
        self.app_mode = default_mode
        self.classification_labels = {}
        self.training_running = False

        self.file_path = None
        self.dir_name = None
        self.m_img_list = []
        self.cur_img_idx = 0
        self.img_count = 0

        self.dirty = False

    def set_image_list(self, image_list):
        self.m_img_list = list(image_list or [])
        self.img_count = len(self.m_img_list)

    def set_current_index(self, index):
        self.cur_img_idx = int(index)

    def set_file_path(self, file_path):
        self.file_path = file_path

    def set_directory(self, dir_name):
        self.dir_name = dir_name

    def set_dirty(self, value):
        self.dirty = bool(value)

    def set_training_running(self, value):
        self.training_running = bool(value)
