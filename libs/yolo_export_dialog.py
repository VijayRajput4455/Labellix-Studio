import os

try:
    from PyQt5.QtWidgets import (
        QCheckBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QSpinBox,
        QVBoxLayout,
    )
except ImportError:
    from PyQt4.QtGui import (
        QCheckBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QSpinBox,
        QVBoxLayout,
    )


class YOLOExportConfigDialog(QDialog):
    def __init__(self, parent=None, title='Export YOLO Dataset', defaults=None, strings=None):
        super(YOLOExportConfigDialog, self).__init__(parent)
        self._strings = strings or {}
        defaults = defaults or {}

        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(560, 360)

        root_layout = QVBoxLayout(self)
        form = QFormLayout()

        self.export_dir_edit = QLineEdit(defaults.get('export_dir', '') or '')
        browse_btn = QPushButton(self._text('browse', 'Browse'))
        browse_btn.clicked.connect(self._browse_export_dir)
        export_dir_row = QHBoxLayout()
        export_dir_row.addWidget(self.export_dir_edit)
        export_dir_row.addWidget(browse_btn)
        form.addRow(self._text('exportDir', 'Export folder'), export_dir_row)

        self.dataset_name_edit = QLineEdit(defaults.get('dataset_name', 'yolo_dataset') or 'yolo_dataset')
        form.addRow(self._text('datasetName', 'Dataset folder name'), self.dataset_name_edit)

        self.train_spin = self._new_percent_spin(defaults.get('train_percent', 80))
        self.test_spin = self._new_percent_spin(defaults.get('test_percent', 10))
        self.valid_spin = self._new_percent_spin(defaults.get('valid_percent', 10))
        self.train_spin.valueChanged.connect(self._update_split_sum)
        self.test_spin.valueChanged.connect(self._update_split_sum)
        self.valid_spin.valueChanged.connect(self._update_split_sum)
        form.addRow(self._text('trainPercent', 'Train (%)'), self.train_spin)
        form.addRow(self._text('testPercent', 'Test (%)'), self.test_spin)
        form.addRow(self._text('validPercent', 'Valid (%)'), self.valid_spin)

        self.split_sum_label = QLabel('')
        form.addRow(self._text('splitSum', 'Split sum'), self.split_sum_label)

        self.stratified_checkbox = QCheckBox(self._text('stratified', 'Use stratified split'))
        self.stratified_checkbox.setChecked(bool(defaults.get('stratified', False)))
        form.addRow('', self.stratified_checkbox)

        self.shuffle_checkbox = QCheckBox(self._text('shuffle', 'Shuffle before split'))
        self.shuffle_checkbox.setChecked(bool(defaults.get('shuffle', True)))
        self.shuffle_checkbox.toggled.connect(self._sync_seed_state)
        form.addRow('', self.shuffle_checkbox)

        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, (2 ** 31) - 1)
        self.seed_spin.setValue(int(defaults.get('seed', 42)))
        form.addRow(self._text('seed', 'Random seed'), self.seed_spin)

        self.preview_checkbox = QCheckBox(self._text('preview', 'Show split preview before export'))
        self.preview_checkbox.setChecked(bool(defaults.get('show_preview', True)))
        form.addRow('', self.preview_checkbox)

        self.zip_checkbox = QCheckBox(self._text('zip', 'Create zip after export'))
        self.zip_checkbox.setChecked(bool(defaults.get('create_zip', False)))
        form.addRow('', self.zip_checkbox)

        root_layout.addLayout(form)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        root_layout.addWidget(self.button_box)

        self._sync_seed_state()
        self._update_split_sum()

    def _text(self, key, fallback):
        value = self._strings.get(key)
        return value if value else fallback

    @staticmethod
    def _new_percent_spin(value):
        spin = QSpinBox()
        spin.setRange(0, 100)
        spin.setValue(int(value))
        return spin

    def _browse_export_dir(self):
        start_dir = self.export_dir_edit.text().strip() or '.'
        chosen = QFileDialog.getExistingDirectory(
            self,
            self._text('chooseExportDirTitle', 'Choose export folder'),
            start_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if chosen:
            self.export_dir_edit.setText(chosen)

    def _sync_seed_state(self):
        self.seed_spin.setEnabled(self.shuffle_checkbox.isChecked())

    def _split_sum(self):
        return self.train_spin.value() + self.test_spin.value() + self.valid_spin.value()

    def _update_split_sum(self):
        total = self._split_sum()
        if total == 100:
            self.split_sum_label.setText(self._text('splitSumOk', '100 (OK)'))
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)
        else:
            self.split_sum_label.setText(self._text('splitSumInvalid', 'Must be 100 (current: %d)') % total)
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)

    def _on_accept(self):
        export_dir = self.export_dir_edit.text().strip()
        dataset_name = self.dataset_name_edit.text().strip()

        if not export_dir:
            QMessageBox.warning(self, self.windowTitle(), self._text('missingExportDir', 'Please choose an export folder.'))
            return
        if not os.path.isdir(export_dir):
            QMessageBox.warning(self, self.windowTitle(), self._text('invalidExportDir', 'Export folder does not exist.'))
            return
        if not dataset_name:
            QMessageBox.warning(self, self.windowTitle(), self._text('missingDatasetName', 'Please enter dataset folder name.'))
            return
        if self._split_sum() != 100:
            QMessageBox.warning(self, self.windowTitle(), self._text('invalidSplit', 'Split ratios must sum to 100.'))
            return
        self.accept()

    def get_config(self):
        if self.exec_() != QDialog.Accepted:
            return None
        return {
            'export_dir': self.export_dir_edit.text().strip(),
            'dataset_name': self.dataset_name_edit.text().strip(),
            'train_percent': self.train_spin.value(),
            'test_percent': self.test_spin.value(),
            'valid_percent': self.valid_spin.value(),
            'stratified': self.stratified_checkbox.isChecked(),
            'shuffle': self.shuffle_checkbox.isChecked(),
            'seed': self.seed_spin.value(),
            'show_preview': self.preview_checkbox.isChecked(),
            'create_zip': self.zip_checkbox.isChecked(),
        }
