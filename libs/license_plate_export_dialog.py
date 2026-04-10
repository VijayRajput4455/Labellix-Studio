import os

try:
    from PyQt5.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QVBoxLayout,
    )
except ImportError:
    from PyQt4.QtGui import (
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QVBoxLayout,
    )


class LicensePlateExportConfigDialog(QDialog):
    def __init__(self, parent=None, title='Export License Plate Dataset', defaults=None, strings=None):
        super(LicensePlateExportConfigDialog, self).__init__(parent)
        self._strings = strings or {}
        defaults = defaults or {}

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(460)
        self.resize(480, 220)

        root_layout = QVBoxLayout(self)
        form = QFormLayout()

        self.export_dir_edit = QLineEdit(defaults.get('export_dir', '') or '')
        browse_btn = QPushButton(self._text('browse', 'Browse'))
        browse_btn.clicked.connect(self._browse_export_dir)
        export_dir_row = QHBoxLayout()
        export_dir_row.addWidget(self.export_dir_edit)
        export_dir_row.addWidget(browse_btn)
        form.addRow(self._text('exportDir', 'Export folder'), export_dir_row)

        self.dataset_name_edit = QLineEdit(defaults.get('dataset_name', 'license_plate_dataset') or 'license_plate_dataset')
        form.addRow(self._text('datasetName', 'Dataset folder name'), self.dataset_name_edit)

        self.transfer_combo = QComboBox()
        self.transfer_combo.addItem(self._text('copyMode', 'Copy'), 'copy')
        self.transfer_combo.addItem(self._text('moveMode', 'Move'), 'move')
        default_mode = defaults.get('transfer_mode', 'copy')
        self.transfer_combo.setCurrentIndex(1 if default_mode == 'move' else 0)
        form.addRow(self._text('transferMode', 'Transfer mode'), self.transfer_combo)

        self.export_mode_combo = None
        if bool(defaults.get('show_image_mode', False)):
            self.export_mode_combo = QComboBox()
            self.export_mode_combo.addItem(self._text('imageModeCropped', 'Cropped plates only'), 'cropped')
            self.export_mode_combo.addItem(self._text('imageModeFull', 'Full image + labels'), 'full')
            default_image_mode = defaults.get('image_mode', 'full')
            self.export_mode_combo.setCurrentIndex(1 if default_image_mode == 'full' else 0)
            form.addRow(self._text('imageMode', 'Image export mode'), self.export_mode_combo)

        self.zip_checkbox = QCheckBox(self._text('zip', 'Create zip after export'))
        self.zip_checkbox.setChecked(bool(defaults.get('create_zip', False)))
        form.addRow('', self.zip_checkbox)

        root_layout.addLayout(form)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        root_layout.addWidget(self.button_box)

    def _text(self, key, fallback):
        value = self._strings.get(key)
        return value if value else fallback

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
        self.accept()

    def get_config(self):
        if self.exec_() != QDialog.Accepted:
            return None
        transfer_mode = self.transfer_combo.itemData(self.transfer_combo.currentIndex())
        image_mode = 'full'
        if self.export_mode_combo is not None:
            image_mode = self.export_mode_combo.itemData(self.export_mode_combo.currentIndex())
        return {
            'export_dir': self.export_dir_edit.text().strip(),
            'dataset_name': self.dataset_name_edit.text().strip(),
            'move_images': transfer_mode == 'move',
            'create_zip': self.zip_checkbox.isChecked(),
            'image_mode': image_mode,
        }
