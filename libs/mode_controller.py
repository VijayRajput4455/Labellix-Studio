#!/usr/bin/env python
# -*- coding: utf-8 -*-

from libs.labelDialog import LabelDialog
from libs.utils import add_actions


class ModeController(object):
    """Owns mode transition and mode-dependent action wiring."""

    def __init__(self, window):
        self.window = window

    def _set_action_checked(self, action, checked):
        action.blockSignals(True)
        action.setChecked(bool(checked))
        action.blockSignals(False)

    def _set_detection_checked(self, checked):
        self._set_action_checked(self.window.actions.detectionMode, checked)

    def _reset_label_dialog_after_classification(self):
        self.window.restore_detection_label_history()
        if not self.window.file_path:
            self.window.label_list.clear()

    def populate_mode_actions(self):
        if self.window.is_classification_mode():
            tool, menu = self.window.actions.classification, self.window.actions.classificationContext
        elif self.window.is_license_plate_mode():
            tool = self.window.actions.beginner if self.window.beginner() else self.window.actions.advanced
            menu = self.window.actions.beginnerContext if self.window.beginner() else self.window.actions.advancedContext
        elif self.window.is_segmentation_mode():
            tool, menu = self.window.actions.segmentation, self.window.actions.segmentationContext
        elif self.window.is_training_mode():
            tool, menu = self.window.actions.training, self.window.actions.trainingContext
        elif self.window.beginner():
            tool, menu = self.window.actions.beginner, self.window.actions.beginnerContext
        else:
            tool, menu = self.window.actions.advanced, self.window.actions.advancedContext

        self.window.tools.clear()
        add_actions(self.window.tools, tool)
        self.window.canvas.menus[0].clear()
        add_actions(self.window.canvas.menus[0], menu)
        self.window.menus.edit.clear()

        if self.window.is_classification_mode():
            add_actions(self.window.menus.edit, self.window.actions.classificationMenu)
        elif self.window.is_training_mode():
            add_actions(self.window.menus.edit, self.window.actions.trainingMenu)
        else:
            actions = (self.window.actions.create,) if self.window.beginner() else (
                self.window.actions.createMode,
                self.window.actions.editMode,
            )
            add_actions(self.window.menus.edit, actions + self.window.actions.editMenu)

        self._set_action_checked(self.window.actions.classificationMode, self.window.is_classification_mode())
        self._set_detection_checked(
            (not self.window.is_classification_mode())
            and (not self.window.is_license_plate_mode())
            and (not self.window.is_segmentation_mode())
            and (not self.window.is_training_mode())
        )
        self._set_action_checked(self.window.actions.segmentationMode, self.window.is_segmentation_mode())
        self._set_action_checked(self.window.actions.licensePlateMode, self.window.is_license_plate_mode())
        self._set_action_checked(self.window.actions.trainingMode, self.window.is_training_mode())

        self.window.canvas.set_segmentation_mode(self.window.is_segmentation_mode())
        self.window.canvas.setEnabled(not self.window.is_training_mode())
        self.window.update_classification_ui()
        self.window.update_shortcut_hints()

    def toggle_detection_mode(self, value=True):
        if not value:
            self._set_detection_checked(
                (not self.window.is_classification_mode())
                and (not self.window.is_license_plate_mode())
                and (not self.window.is_segmentation_mode())
                and (not self.window.is_training_mode())
            )
            return

        if not self.window.is_classification_mode() and not self.window.is_license_plate_mode() and not self.window.is_segmentation_mode() and not self.window.is_training_mode():
            self.populate_mode_actions()
            self.window.update_status_chips()
            return

        if self.window.dirty and not self.window.may_continue():
            self._set_detection_checked(False)
            return

        was_classification = self.window.is_classification_mode()
        self.window.app_mode = self.window.DETECTION_MODE
        self._set_action_checked(self.window.actions.classificationMode, False)
        self._set_action_checked(self.window.actions.licensePlateMode, False)
        self._set_action_checked(self.window.actions.segmentationMode, False)
        self._set_action_checked(self.window.actions.trainingMode, False)
        self._set_detection_checked(True)

        if was_classification:
            self._reset_label_dialog_after_classification()

        self.populate_mode_actions()
        if self.window.file_path:
            self.window.load_file(self.window.file_path)
        else:
            self.window.update_classification_ui()
        self.window.update_status_chips()

    def toggle_classification_mode(self, value=True):
        if bool(value) == self.window.is_classification_mode():
            self._set_action_checked(self.window.actions.classificationMode, bool(value))
            self.populate_mode_actions()
            self.window.update_status_chips()
            return

        if self.window.dirty and not self.window.may_continue():
            self._set_action_checked(self.window.actions.classificationMode, self.window.is_classification_mode())
            return

        if value:
            self.window.cache_detection_label_history()

        self.window.app_mode = self.window.CLASSIFICATION_MODE if value else self.window.DETECTION_MODE
        self._set_action_checked(self.window.actions.classificationMode, bool(value))
        if value:
            self._set_action_checked(self.window.actions.licensePlateMode, False)
            self._set_action_checked(self.window.actions.segmentationMode, False)
            self._set_action_checked(self.window.actions.trainingMode, False)

        if self.window.is_classification_mode():
            self.window.load_classification_manifest(self.window.classification_source_dir())
        else:
            self._reset_label_dialog_after_classification()

        self.populate_mode_actions()
        if self.window.file_path:
            self.window.load_file(self.window.file_path)
        else:
            self.window.update_classification_ui()
        self.window.update_status_chips()

    def toggle_license_plate_mode(self, value=True):
        if bool(value) == self.window.is_license_plate_mode():
            self._set_action_checked(self.window.actions.licensePlateMode, bool(value))
            self.populate_mode_actions()
            self.window.update_status_chips()
            return

        if self.window.dirty and not self.window.may_continue():
            self._set_action_checked(self.window.actions.licensePlateMode, self.window.is_license_plate_mode())
            return

        was_classification = self.window.is_classification_mode()
        self.window.app_mode = self.window.LICENSE_PLATE_MODE if value else self.window.DETECTION_MODE
        self._set_action_checked(self.window.actions.licensePlateMode, bool(value))
        if value:
            self._set_action_checked(self.window.actions.classificationMode, False)
            self._set_action_checked(self.window.actions.segmentationMode, False)
            self._set_action_checked(self.window.actions.trainingMode, False)

        if was_classification:
            self._reset_label_dialog_after_classification()

        self.populate_mode_actions()
        if self.window.file_path:
            self.window.load_file(self.window.file_path)
        else:
            self.window.update_classification_ui()
        self.window.update_status_chips()

    def toggle_segmentation_mode(self, value=True):
        if bool(value) == self.window.is_segmentation_mode():
            self._set_action_checked(self.window.actions.segmentationMode, bool(value))
            self.populate_mode_actions()
            self.window.update_status_chips()
            return

        if self.window.dirty and not self.window.may_continue():
            self._set_action_checked(self.window.actions.segmentationMode, self.window.is_segmentation_mode())
            return

        was_classification = self.window.is_classification_mode()
        self.window.app_mode = self.window.SEGMENTATION_MODE if value else self.window.DETECTION_MODE
        self._set_action_checked(self.window.actions.segmentationMode, bool(value))
        if value:
            self._set_action_checked(self.window.actions.classificationMode, False)
            self._set_action_checked(self.window.actions.licensePlateMode, False)
            self._set_action_checked(self.window.actions.trainingMode, False)

        if was_classification:
            self._reset_label_dialog_after_classification()

        self.populate_mode_actions()
        if self.window.file_path:
            self.window.load_file(self.window.file_path)
        else:
            self.window.update_classification_ui()
        self.window.update_status_chips()

    def toggle_training_mode(self, value=True):
        if bool(value) == self.window.is_training_mode():
            self._set_action_checked(self.window.actions.trainingMode, bool(value))
            self.populate_mode_actions()
            self.window.update_status_chips()
            return

        if self.window.dirty and not self.window.may_continue():
            self._set_action_checked(self.window.actions.trainingMode, self.window.is_training_mode())
            return

        self.window.app_mode = self.window.TRAINING_MODE if value else self.window.DETECTION_MODE
        self._set_action_checked(self.window.actions.trainingMode, bool(value))
        if value:
            self._set_action_checked(self.window.actions.classificationMode, False)
            self._set_action_checked(self.window.actions.licensePlateMode, False)
            self._set_action_checked(self.window.actions.segmentationMode, False)
            self._set_detection_checked(False)
            self.window._refresh_training_panel_defaults()
        else:
            self._set_detection_checked(True)

        self.populate_mode_actions()
        self.window.update_status_chips()
