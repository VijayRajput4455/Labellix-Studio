from libs.labelDialog import LabelDialog
from libs.utils import trimmed


class ClassificationWorkflowsMixin(object):
    """Classification class-management workflows extracted from MainWindow."""

    def current_classification_label(self):
        if not self.file_path:
            return None
        return self.classification_labels.get(self.file_path)

    def set_classification_label(self, label):
        if not self.file_path:
            return False

        normalized_label = trimmed(label)
        if not normalized_label:
            return False

        added_new_class = False
        if normalized_label not in self.label_hist:
            self.ensure_label_in_history(normalized_label)
            if normalized_label not in self.base_label_hist:
                self.base_label_hist.append(normalized_label)
                self.base_label_hist.sort(key=lambda value: value.lower())
                added_new_class = True

        if added_new_class:
            self._write_predefined_classes_file(
                self.classification_predefined_classes_file,
                self.base_label_hist,
            )

        assigned_label = self.classification_service.assign_label(
            file_path=self.file_path,
            label=normalized_label,
            label_hist=self.label_hist,
            classification_labels=self.classification_labels,
        )
        if assigned_label is None:
            self.error_message(self.get_str('classificationManifestError'), self.get_str('classificationInvalidClass'))
            return False

        self.prev_label_text = assigned_label
        self.set_dirty()
        self.update_classification_ui()
        return self.save_file()

    def assign_classification_label(self, _value=False):
        if not self.is_classification_mode() or not self.file_path:
            return

        current_label = self.current_classification_label() or self.prev_label_text
        self.label_dialog = LabelDialog(parent=self, list_item=self.label_hist)
        label = self.label_dialog.pop_up(text=current_label)
        if label is not None:
            self.set_classification_label(label)

    def add_classification_class(self, _value=False):
        if not self.is_classification_mode():
            return

        self.label_dialog = LabelDialog(parent=self, list_item=self.label_hist)
        label = self.label_dialog.pop_up(text='')
        normalized_label = trimmed(label) if label is not None else ''
        if not normalized_label:
            return

        if normalized_label not in self.label_hist:
            self.label_hist.append(normalized_label)
            self.label_hist.sort(key=lambda value: value.lower())
        if normalized_label not in self.base_label_hist:
            self.base_label_hist.append(normalized_label)
            self.base_label_hist.sort(key=lambda value: value.lower())

        self._write_predefined_classes_file(
            self.classification_predefined_classes_file,
            self.base_label_hist,
        )
        self._update_label_history_widgets(preferred_label=normalized_label)
        self.set_dirty()
        self.update_classification_ui()
        self.save_file()

    def rename_selected_classification_class(self, _value=False):
        if not self.is_classification_mode():
            return

        item = self.current_item()
        if not item:
            return

        old_label = trimmed(item.text())
        if not old_label:
            return

        self.label_dialog = LabelDialog(parent=self, list_item=self.label_hist)
        new_label = self.label_dialog.pop_up(text=old_label)
        new_label = trimmed(new_label) if new_label is not None else ''
        if not new_label or new_label == old_label:
            return

        if new_label in self.label_hist:
            self.error_message(
                self.get_str('classificationManifestError'),
                self.get_str('classificationInvalidClass')
            )
            return

        self.label_hist = [new_label if trimmed(label) == old_label else label for label in self.label_hist]
        self.base_label_hist = [new_label if trimmed(label) == old_label else label for label in self.base_label_hist]
        self.label_hist = sorted({trimmed(label) for label in self.label_hist if trimmed(label)}, key=lambda value: value.lower())
        self.base_label_hist = sorted({trimmed(label) for label in self.base_label_hist if trimmed(label)}, key=lambda value: value.lower())

        for image_path, class_label in list(self.classification_labels.items()):
            if trimmed(class_label) == old_label:
                self.classification_labels[image_path] = new_label

        self._write_predefined_classes_file(
            self.classification_predefined_classes_file,
            self.base_label_hist,
        )
        self._update_label_history_widgets(preferred_label=new_label)
        self.set_dirty()
        self.update_classification_ui()
        self.save_file()

    def clear_classification_label(self, _value=False):
        if not self.is_classification_mode() or not self.file_path:
            return

        if self.classification_service.clear_label(self.file_path, self.classification_labels):
            self.set_dirty()
            self.update_classification_ui()
            self.save_file()

    def open_next_unlabeled_image(self, _value=False):
        if not self.is_classification_mode() or not self.m_img_list:
            return

        start_index = self.cur_img_idx + 1 if self.file_path else 0
        next_index = self.classification_service.next_unlabeled_index(
            image_paths=self.m_img_list,
            classification_labels=self.classification_labels,
            start_index=start_index,
        )
        if next_index is not None:
            self.cur_img_idx = next_index
            self.load_file(self.m_img_list[next_index])
            return

        self.status(self.get_str('classificationDone'))
