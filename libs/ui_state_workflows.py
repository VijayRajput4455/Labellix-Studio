try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QBrush
    from PyQt5.QtWidgets import QListWidgetItem
except ImportError:
    from PyQt4.QtCore import Qt
    from PyQt4.QtGui import QBrush, QListWidgetItem

from libs.utils import generate_color_by_text


class UIStateWorkflowsMixin(object):
    """UI state synchronization helpers extracted from MainWindow."""

    def populate_classification_label_list(self):
        if not self.is_classification_mode():
            return

        current_label = self.current_classification_label()
        self.label_list.blockSignals(True)
        self.label_list.clear()
        for label in self.label_hist:
            item = QListWidgetItem(label)
            item.setBackground(generate_color_by_text(label))
            self.label_list.addItem(item)
            if label == current_label:
                item.setSelected(True)
        self.label_list.blockSignals(False)

    def refresh_file_list_classification_state(self):
        if not self.is_classification_mode() or self.file_list_widget.count() != len(self.m_img_list):
            return

        for index, image_path in enumerate(self.m_img_list):
            item = self.file_list_widget.item(index)
            label = self.classification_labels.get(image_path)
            if label:
                item.setBackground(generate_color_by_text(label))
                item.setToolTip('%s: %s' % (self.get_str('classificationCurrent'), label))
            else:
                item.setBackground(QBrush())
                item.setToolTip(self.get_str('classificationNone'))

    def _update_classification_button_style(self):
        buttons = (
            self.classification_add_button,
            self.classification_rename_button,
            self.classification_remove_button,
            self.classification_assign_button,
            self.classification_clear_button,
            self.classification_export_button,
        )
        style = Qt.ToolButtonTextBesideIcon
        for button in buttons:
            button.setToolButtonStyle(style)
            action = button.defaultAction()
            if action is not None:
                button.setToolTip(action.text())

    def update_classification_ui(self):
        is_classification_mode = self.is_classification_mode()
        is_license_plate_mode = self.is_license_plate_mode()
        is_training_mode = self.is_training_mode()
        has_image = not self.image.isNull()
        has_selected_shape = bool(self.canvas.selected_shape) if self.canvas is not None else False

        self.use_default_label_container.setVisible((not is_classification_mode) and (not is_license_plate_mode) and (not is_training_mode))
        self.diffc_button.setVisible((not is_classification_mode) and (not is_license_plate_mode) and (not is_training_mode))
        self.lock_predefined_classes_container.setVisible((not is_classification_mode) and (not is_license_plate_mode) and (not is_training_mode))
        self.edit_button.setVisible((not is_classification_mode) and (not is_training_mode) and not self.actions.advancedMode.isChecked())
        self.combo_box.setVisible((not is_classification_mode) and (not is_training_mode))
        self.classification_current_label.setVisible(is_classification_mode)
        self.classification_progress_label.setVisible(is_classification_mode)
        self.classification_buttons_container.setVisible(is_classification_mode)
        self._update_classification_button_style()
        self.dock.setVisible(not is_training_mode)
        self.file_dock.setVisible(not is_training_mode)
        target_index = 1 if is_training_mode else 0
        if self.central_stack.currentIndex() != target_index:
            self.central_stack.setCurrentIndex(target_index)
            self._animate_widget_fade_in(self.central_stack.currentWidget(), self._motion_profile().get('panel_fade_ms', 180))
        if is_training_mode:
            self.training_config_panel._apply_panel_style()
        self.training_log_dock.setVisible(is_training_mode or self.training_running)

        self.actions.advancedMode.setEnabled((not is_classification_mode) and (not is_training_mode))
        self.actions.save_format.setEnabled((not is_classification_mode) and (not is_license_plate_mode) and (not is_training_mode))
        self.actions.saveAs.setEnabled((not is_classification_mode) and (not is_training_mode) and bool(self.items_to_shapes))
        self.actions.create.setEnabled((not is_classification_mode) and (not is_training_mode) and has_image)
        self.actions.createMode.setEnabled((not is_classification_mode) and (not is_training_mode) and has_image)
        self.actions.drawPolygon.setEnabled((not is_classification_mode) and (not is_training_mode) and has_image)
        self.actions.editMode.setEnabled((not is_classification_mode) and (not is_training_mode) and has_image)
        self.actions.delete.setEnabled((not is_classification_mode) and (not is_training_mode) and has_selected_shape)
        self.actions.copy.setEnabled((not is_classification_mode) and (not is_training_mode) and has_selected_shape)
        self.actions.edit.setEnabled((not is_classification_mode) and (not is_training_mode) and has_selected_shape)
        self.actions.shapeLineColor.setEnabled((not is_classification_mode) and (not is_training_mode) and has_selected_shape)
        self.actions.shapeFillColor.setEnabled((not is_classification_mode) and (not is_training_mode) and has_selected_shape)
        self.actions.verify.setEnabled((not is_classification_mode) and (not is_training_mode) and has_image)
        self.actions.addClass.setEnabled(is_classification_mode)
        self.actions.renameClass.setEnabled(is_classification_mode and self.current_item() is not None)
        self.actions.removeClass.setEnabled(is_classification_mode and self.current_item() is not None)
        self.actions.assignClass.setEnabled(is_classification_mode and has_image)
        self.actions.clearClass.setEnabled(is_classification_mode and self.current_classification_label() is not None)
        self.actions.exportClasses.setEnabled(is_classification_mode and self.img_count > 0)
        self.actions.exportLicensePlateDataset.setEnabled(is_license_plate_mode and self.img_count > 0)
        self.actions.exportYOLODataset.setEnabled((not is_classification_mode) and (not is_license_plate_mode) and (not is_training_mode) and self.img_count > 0)
        self.actions.trainYOLOv8.setEnabled((not self.training_running) and (not is_training_mode))
        mode_switch_enabled = not self.training_running
        self.actions.detectionMode.setEnabled(mode_switch_enabled)
        self.actions.classificationMode.setEnabled(mode_switch_enabled)
        self.actions.licensePlateMode.setEnabled(mode_switch_enabled)
        self.actions.segmentationMode.setEnabled(mode_switch_enabled)
        self.actions.trainingMode.setEnabled(mode_switch_enabled)
        self.actions.stopTraining.setEnabled(self.training_running)
        self.training_config_panel.set_running_state(self.training_running)
        self.actions.nextUnlabeled.setEnabled(is_classification_mode and self.img_count > 0)
        self.update_history_actions()

        self.dock.setWindowTitle(self.get_str('classificationClasses') if is_classification_mode else self.get_str('boxLabelText'))

        if is_classification_mode:
            current_label = self.current_classification_label() or self.get_str('classificationNone')
            labeled_count = len([image_path for image_path in self.m_img_list if self.classification_labels.get(image_path)])
            self.classification_current_label.setText('%s: %s' % (self.get_str('classificationCurrent'), current_label))
            self.classification_progress_label.setText('%s: %d / %d' % (self.get_str('classificationProgress'), labeled_count, self.img_count))
            self.populate_classification_label_list()
            self.refresh_file_list_classification_state()
