import os

try:
    from PyQt5.QtWidgets import (
        QDialog,
        QVBoxLayout,
        QHBoxLayout,
        QFormLayout,
        QRadioButton,
        QButtonGroup,
        QLineEdit,
        QPushButton,
        QComboBox,
        QSpinBox,
        QDialogButtonBox,
        QLabel,
        QFrame,
        QFileDialog,
        QMessageBox,
        QPlainTextEdit,
        QScrollArea,
        QWidget,
    )
    from PyQt5.QtCore import Qt, pyqtSignal
    from PyQt5.QtGui import QColor
except ImportError:
    from PyQt4.QtGui import (
        QDialog,
        QVBoxLayout,
        QHBoxLayout,
        QFormLayout,
        QRadioButton,
        QButtonGroup,
        QLineEdit,
        QPushButton,
        QComboBox,
        QSpinBox,
        QDialogButtonBox,
        QLabel,
        QFrame,
        QFileDialog,
        QMessageBox,
        QPlainTextEdit,
        QScrollArea,
        QWidget,
    )
    from PyQt4.QtCore import Qt, pyqtSignal

from libs.training_runner import build_yolov8_train_command, format_command_for_display, TrainingCommandError
from styletheame import PALETTES
from libs.utils import new_icon


class TrainConfigPanel(QWidget):
    startRequested = pyqtSignal(dict)
    cancelRequested = pyqtSignal()

    def __init__(self, parent=None, defaults=None):
        super(TrainConfigPanel, self).__init__(parent)
        self.defaults = defaults or {}
        self._running = False
        self._build_ui()
        self._apply_panel_style()
        self.set_defaults(self.defaults)
        self._wire_signals()
        self._refresh_command_preview()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 12)
        root.setSpacing(10)

        # ── Header ────────────────────────────────────────────────────────
        self.header_title = QLabel('Train YOLOv8')
        self.header_title.setObjectName('trainHeaderTitle')
        self.header_subtitle = QLabel(
            'Configure your dataset source and training parameters, then press \u201cStart Training\u201d.')
        self.header_subtitle.setObjectName('trainHeaderSubtitle')
        root.addWidget(self.header_title)
        root.addWidget(self.header_subtitle)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName('headerSep')
        root.addWidget(sep)

        # ── Two-column body ───────────────────────────────────────────────
        body = QHBoxLayout()
        body.setSpacing(20)
        root.addLayout(body, stretch=1)

        # ── LEFT COLUMN ───────────────────────────────────────────────────
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QScrollArea.NoFrame)
        left_content = QWidget()
        left_layout = QVBoxLayout(left_content)
        left_layout.setContentsMargins(0, 4, 8, 4)
        left_layout.setSpacing(18)

        def _section_label(text):
            lbl = QLabel(text)
            lbl.setObjectName('sectionLabel')
            return lbl

        def _field_label(text):
            lbl = QLabel(text)
            lbl.setObjectName('fieldLabel')
            return lbl

        def _field_col(label_text, widget):
            col = QVBoxLayout()
            col.setSpacing(4)
            col.addWidget(_field_label(label_text))
            col.addWidget(widget)
            return col

        # ── Dataset Source ─────────────────────────────────────────────
        left_layout.addWidget(_section_label('\u25a0  Dataset Source'))

        ds_card = QWidget()
        ds_card.setObjectName('card')
        ds_vbox = QVBoxLayout(ds_card)
        ds_vbox.setContentsMargins(14, 14, 14, 14)
        ds_vbox.setSpacing(10)

        self.radio_last_export = QRadioButton('Use last exported dataset.yaml')
        self.radio_existing_yaml = QRadioButton('Use existing dataset.yaml file')
        self.source_mode_group = QButtonGroup(self)
        self.source_mode_group.addButton(self.radio_last_export)
        self.source_mode_group.addButton(self.radio_existing_yaml)

        self.last_export_label = QLabel('Last export: (not set)')
        self.last_export_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.last_export_label.setObjectName('lastExportLabel')

        yaml_row = QHBoxLayout()
        yaml_row.setSpacing(8)
        self.yaml_path_edit = QLineEdit()
        self.yaml_path_edit.setPlaceholderText('Path to dataset.yaml…')
        self.yaml_browse_button = QPushButton('Browse…')
        self.yaml_browse_button.setObjectName('browseBtn')
        yaml_row.addWidget(self.yaml_path_edit)
        yaml_row.addWidget(self.yaml_browse_button)

        ds_vbox.addWidget(self.radio_last_export)
        ds_vbox.addWidget(self.last_export_label)

        ds_sep = QFrame(); ds_sep.setFrameShape(QFrame.HLine); ds_sep.setObjectName('cardSep')
        ds_vbox.addWidget(ds_sep)

        ds_vbox.addWidget(self.radio_existing_yaml)
        ds_vbox.addLayout(yaml_row)
        left_layout.addWidget(ds_card)

        # ── Basic Settings ─────────────────────────────────────────────
        left_layout.addWidget(_section_label('\u25a0  Basic Settings'))

        bs_card = QWidget()
        bs_card.setObjectName('card')
        bs_inner = QVBoxLayout(bs_card)
        bs_inner.setContentsMargins(14, 14, 14, 14)
        bs_inner.setSpacing(12)

        # Output dir — full width
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText('Project output folder…')
        self.output_browse_button = QPushButton('Browse…')
        self.output_browse_button.setObjectName('browseBtn')
        out_row_h = QHBoxLayout(); out_row_h.setSpacing(8)
        out_row_h.addWidget(self.output_dir_edit)
        out_row_h.addWidget(self.output_browse_button)
        out_row_v = QVBoxLayout(); out_row_v.setSpacing(4)
        out_row_v.addWidget(_field_label('Output Directory'))
        out_row_v.addLayout(out_row_h)
        bs_inner.addLayout(out_row_v)

        # Run name + Model size — side by side
        self.run_name_edit = QLineEdit()
        self.run_name_edit.setPlaceholderText('e.g. train_exp')
        self.model_combo = QComboBox()
        self.model_combo.addItems(['nano', 'small', 'medium', 'large', 'xlarge'])

        row2 = QHBoxLayout(); row2.setSpacing(16)
        row2.addLayout(_field_col('Run Name', self.run_name_edit), stretch=1)
        row2.addLayout(_field_col('Model Size', self.model_combo), stretch=1)
        bs_inner.addLayout(row2)

        # CLI — full width
        self.cli_edit = QLineEdit()
        self.cli_edit.setPlaceholderText('e.g.  yolo   or   /usr/local/bin/yolo')
        bs_inner.addLayout(_field_col('CLI Executable', self.cli_edit))

        left_layout.addWidget(bs_card)

        # ── Advanced Settings ──────────────────────────────────────────
        left_layout.addWidget(_section_label('\u25a0  Advanced Settings'))

        av_card = QWidget()
        av_card.setObjectName('card')
        av_inner = QVBoxLayout(av_card)
        av_inner.setContentsMargins(14, 14, 14, 14)
        av_inner.setSpacing(12)

        self.epochs_spin = QSpinBox(); self.epochs_spin.setRange(1, 100000)
        self.batch_spin = QSpinBox(); self.batch_spin.setRange(1, 4096)
        self.image_size_spin = QSpinBox(); self.image_size_spin.setRange(32, 4096)
        self.patience_spin = QSpinBox(); self.patience_spin.setRange(0, 100000)
        self.device_edit = QLineEdit(); self.device_edit.setPlaceholderText('cpu / 0 / 0,1')
        self.workers_spin = QSpinBox(); self.workers_spin.setRange(0, 256)
        self.extra_args_edit = QLineEdit(); self.extra_args_edit.setPlaceholderText('e.g. --amp --cos-lr')

        # Row: Epochs / Batch / Image size / Patience
        row_spins = QHBoxLayout(); row_spins.setSpacing(16)
        row_spins.addLayout(_field_col('Epochs', self.epochs_spin), stretch=1)
        row_spins.addLayout(_field_col('Batch Size', self.batch_spin), stretch=1)
        row_spins.addLayout(_field_col('Image Size', self.image_size_spin), stretch=1)
        row_spins.addLayout(_field_col('Patience', self.patience_spin), stretch=1)
        av_inner.addLayout(row_spins)

        # Row: Device / Workers
        row_dw = QHBoxLayout(); row_dw.setSpacing(16)
        row_dw.addLayout(_field_col('Device', self.device_edit), stretch=1)
        row_dw.addLayout(_field_col('Workers', self.workers_spin), stretch=1)
        av_inner.addLayout(row_dw)

        # Extra args — full width
        av_inner.addLayout(_field_col('Extra Args', self.extra_args_edit))

        left_layout.addWidget(av_card)
        left_layout.addStretch(1)
        left_scroll.setWidget(left_content)

        # ── RIGHT COLUMN — Command Preview ────────────────────────────────
        right_col = QVBoxLayout()
        right_col.setSpacing(8)
        right_col.addWidget(_section_label('\u25a0  Command Preview'))

        preview_card = QWidget()
        preview_card.setObjectName('card')
        preview_inner = QVBoxLayout(preview_card)
        preview_inner.setContentsMargins(12, 12, 12, 12)
        preview_inner.setSpacing(0)
        self.command_preview = QPlainTextEdit()
        self.command_preview.setReadOnly(True)
        self.command_preview.setMaximumBlockCount(500)
        preview_inner.addWidget(self.command_preview)
        right_col.addWidget(preview_card, stretch=1)

        body.addWidget(left_scroll, stretch=56)
        body.addLayout(right_col, stretch=44)

        # ── Button bar ────────────────────────────────────────────────────
        btn_sep = QFrame(); btn_sep.setFrameShape(QFrame.HLine); btn_sep.setObjectName('headerSep')
        root.addWidget(btn_sep)
        self.button_box = QDialogButtonBox()
        self.cancel_button = self.button_box.addButton('\u2190 Back to Labeling', QDialogButtonBox.RejectRole)
        self.start_button = self.button_box.addButton('\u25b6  Start Training', QDialogButtonBox.AcceptRole)
        self.cancel_button.setIcon(new_icon('undo'))
        self.start_button.setIcon(new_icon('verify'))
        self.cancel_button.setObjectName('trainSecondaryButton')
        self.start_button.setObjectName('trainPrimaryButton')
        root.addWidget(self.button_box)

    def _apply_panel_style(self):
        theme_name = getattr(self.parent(), 'current_theme', 'futuristic') if self.parent() is not None else 'futuristic'
        p = PALETTES.get(theme_name, PALETTES['futuristic'])
        bg = p['bg']
        bg2 = p['bg2']
        bg3 = p['bg3']
        fg = p['fg']
        fg2 = p['fg2']
        acc = p['acc']
        acc2 = p['acc2']
        border = p['border']
        sel_bg = p['sel_bg']
        is_light_theme = QColor(bg).lightness() >= 145

        if is_light_theme:
            card_bg = '#ffffff'
            input_bg = '#f4f8fd'
            disabled_bg = '#edf2f7'
            preview_bg = '#f8fbff'
            preview_fg = '#2f78b2'
            section_fg = '#2f78b2'
            last_export_fg = '#6e89a5'
        else:
            card_bg = bg2
            input_bg = bg3
            disabled_bg = bg
            preview_bg = bg
            preview_fg = acc
            section_fg = acc2
            last_export_fg = fg2

        ss = (
            # Base
            'QWidget { background: %s; color: %s; }' % (bg, fg) +

            # Header labels
            'QLabel#trainHeaderTitle {'
            ' font-size: 26px; font-weight: 800; color: %s; padding-bottom: 4px; background: transparent;'
            '}' % fg +
            'QLabel#trainHeaderSubtitle {'
            ' font-size: 13px; color: %s; background: transparent;'
            '}' % fg2 +

            # Separator lines
            'QFrame#headerSep { background: %s; max-height: 1px; border: none; }' % border +
            'QFrame#cardSep   { background: %s; max-height: 1px; border: none; }' % border +

            # Section heading (Dataset Source ...)
            'QLabel#sectionLabel {'
            ' font-size: 11px; font-weight: 700; letter-spacing: 1px;'
            ' color: %s; background: transparent; padding: 0;'
            '}' % section_fg +

            # Small label above each field
            'QLabel#fieldLabel {'
            ' font-size: 11px; font-weight: 600; color: %s;'
            ' background: transparent; padding: 0;'
            '}' % fg2 +

            # Last-export path hint
            'QLabel#lastExportLabel {'
            ' font-size: 11px; color: %s; background: transparent; padding-left: 26px;'
            '}' % last_export_fg +

            # Card containers
            'QWidget#card {'
            ' background: %s; border: 1px solid %s; border-radius: 8px;'
            '}' % (card_bg, border) +

            # All other labels inside cards
            'QLabel { color: %s; background: transparent; }' % fg +

            # Radio buttons
            'QRadioButton { color: %s; font-size: 13px; spacing: 10px; background: transparent; }' % fg +
            'QRadioButton::indicator {'
            ' width: 15px; height: 15px; border: 2px solid %s;'
            ' border-radius: 8px; background: %s;'
            '}' % (border, bg3) +
            'QRadioButton::indicator:checked { background: %s; border-color: %s; }' % (acc2, acc) +
            'QRadioButton::indicator:hover   { border-color: %s; }' % acc +

            # Inputs
            'QLineEdit, QSpinBox, QComboBox {'
            ' background: %s; color: %s;'
            ' border: 1px solid %s; border-radius: 6px;'
            ' padding: 8px 12px; min-height: 28px;'
            ' font-size: 13px; selection-background-color: %s;'
            '}' % (input_bg, fg, border, acc2) +
            'QLineEdit:focus, QSpinBox:focus, QComboBox:focus {'
            ' border: 2px solid %s; background: %s;'
            '}' % (acc, bg2) +
            'QLineEdit:hover, QSpinBox:hover, QComboBox:hover { border-color: %s; }' % acc2 +
            'QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {'
            ' background: %s; color: %s; border-color: %s;'
            '}' % (disabled_bg, border, border) +

            # Command preview mono text
            'QPlainTextEdit {'
            ' background: %s; color: %s; border: 1px solid %s; border-radius: 6px;'
            ' padding: 10px; font-family: monospace; font-size: 12px;'
            ' selection-background-color: %s;'
            '}' % (preview_bg, preview_fg, border, sel_bg) +

            # Spinbox arrows
            'QSpinBox::up-button, QSpinBox::down-button { background: %s; border: none; width: 20px; }' % bg2 +
            'QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: %s; }' % sel_bg +

            # ComboBox dropdown
            'QComboBox::drop-down { border: none; width: 26px; background: %s; border-radius: 0 4px 4px 0; }' % bg2 +
            'QComboBox QAbstractItemView {'
            ' background: %s; color: %s;'
            ' selection-background-color: %s; border: 1px solid %s;'
            '}' % (input_bg, fg, acc2, border) +

            # Browse buttons
            'QPushButton#browseBtn {'
            ' background: %s; color: %s;'
            ' border: 1px solid %s; border-radius: 6px;'
            ' padding: 8px 14px; min-width: 82px; font-size: 12px;'
            '}' % (bg2, fg, border) +
            'QPushButton#browseBtn:hover { background: %s; border-color: %s; }' % (sel_bg, acc2) +
            'QPushButton#browseBtn:disabled { background: %s; color: %s; border-color: %s; }' % (bg, border, border) +

            # Generic buttons
            'QPushButton {'
            ' background: %s; color: %s;'
            ' border: 1px solid %s; border-radius: 6px;'
            ' padding: 9px 18px; min-width: 120px;'
            ' font-size: 13px; font-weight: 700;'
            '}' % (acc2, p['sel_fg'], acc) +
            'QPushButton:hover   { background: %s; border-color: %s; }' % (acc, acc2) +
            'QPushButton:pressed { background: %s; }' % acc2 +
            'QPushButton:disabled { background: %s; color: %s; border-color: %s; }' % (bg, border, border) +

            # Dialog button bar
            'QDialogButtonBox QPushButton { min-width: 90px; min-height: 28px; padding: 4px 16px; font-size: 13px; }' +

            # Scrollbar
            'QScrollBar:vertical { background: %s; width: 8px; margin: 0; }' % bg +
            'QScrollBar::handle:vertical { background: %s; border-radius: 4px; min-height: 30px; }' % border +
            'QScrollBar::handle:vertical:hover { background: %s; }' % acc2 +
            'QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }'

            # Scroll area transparency
            'QScrollArea, QScrollArea > QWidget > QWidget { border: none; background: transparent; }'
        )
        self.setStyleSheet(ss)

    def refresh_icons(self):
        self.cancel_button.setIcon(new_icon('undo'))
        self.start_button.setIcon(new_icon('verify'))

    def set_defaults(self, defaults):
        self.defaults = defaults or {}
        mode = self.defaults.get('source_mode', 'last_export')
        last_export_yaml = self.defaults.get('last_export_yaml', '')
        yaml_path = self.defaults.get('yaml_path', '')

        self.last_export_label.setText('Last export: %s' % (last_export_yaml if last_export_yaml else '(not set)'))
        self.yaml_path_edit.setText(yaml_path)
        self.radio_existing_yaml.setChecked(mode == 'existing_yaml')
        self.radio_last_export.setChecked(mode != 'existing_yaml')
        self.cli_edit.setText(self.defaults.get('cli_executable', 'yolo'))
        self.output_dir_edit.setText(self.defaults.get('output_dir', os.getcwd()))
        self.run_name_edit.setText(self.defaults.get('run_name', 'train_exp'))

        model_size = self.defaults.get('model_size', 'nano')
        idx = self.model_combo.findText(model_size)
        self.model_combo.setCurrentIndex(0 if idx < 0 else idx)

        self.epochs_spin.setValue(int(self.defaults.get('epochs', 100)))
        self.batch_spin.setValue(int(self.defaults.get('batch_size', 16)))
        self.image_size_spin.setValue(int(self.defaults.get('image_size', 640)))
        self.patience_spin.setValue(int(self.defaults.get('patience', 50)))
        self.device_edit.setText(self.defaults.get('device', 'cpu'))
        self.workers_spin.setValue(int(self.defaults.get('workers', 8)))
        self.extra_args_edit.setText(self.defaults.get('extra_args', ''))
        self._update_source_widgets()

    def _wire_signals(self):
        self.radio_last_export.toggled.connect(self._update_source_widgets)
        self.radio_existing_yaml.toggled.connect(self._update_source_widgets)
        self.yaml_browse_button.clicked.connect(self._browse_yaml)
        self.output_browse_button.clicked.connect(self._browse_output_dir)
        self.start_button.clicked.connect(self._emit_start)
        self.cancel_button.clicked.connect(self.cancelRequested.emit)

        widgets = [
            self.yaml_path_edit,
            self.cli_edit,
            self.output_dir_edit,
            self.run_name_edit,
            self.device_edit,
            self.extra_args_edit,
            self.model_combo,
            self.epochs_spin,
            self.batch_spin,
            self.image_size_spin,
            self.patience_spin,
            self.workers_spin,
        ]
        for widget in widgets:
            if hasattr(widget, 'textChanged'):
                widget.textChanged.connect(self._refresh_command_preview)
            if hasattr(widget, 'valueChanged'):
                widget.valueChanged.connect(self._refresh_command_preview)
            if hasattr(widget, 'currentIndexChanged'):
                widget.currentIndexChanged.connect(self._refresh_command_preview)

    def _update_source_widgets(self):
        use_existing = self.radio_existing_yaml.isChecked()
        self.yaml_path_edit.setEnabled(use_existing)
        self.yaml_browse_button.setEnabled(use_existing)
        self._refresh_command_preview()

    def _browse_yaml(self):
        yaml_path = QFileDialog.getOpenFileName(self, 'Select dataset.yaml', self.yaml_path_edit.text(), 'YAML Files (*.yaml *.yml)')
        if isinstance(yaml_path, tuple):
            yaml_path = yaml_path[0]
        if yaml_path:
            self.yaml_path_edit.setText(yaml_path)

    def _browse_output_dir(self):
        output_dir = QFileDialog.getExistingDirectory(self, 'Select output project directory', self.output_dir_edit.text())
        if output_dir:
            self.output_dir_edit.setText(output_dir)

    def _selected_yaml(self):
        if self.radio_last_export.isChecked():
            return self.defaults.get('last_export_yaml', '')
        return self.yaml_path_edit.text().strip()

    def current_config(self):
        yaml_path = self._selected_yaml()
        config = {
            'source_mode': 'last_export' if self.radio_last_export.isChecked() else 'existing_yaml',
            'yaml_path': yaml_path,
            'cli_executable': self.cli_edit.text().strip() or 'yolo',
            'output_dir': self.output_dir_edit.text().strip(),
            'run_name': self.run_name_edit.text().strip(),
            'model_size': self.model_combo.currentText(),
            'epochs': self.epochs_spin.value(),
            'batch_size': self.batch_spin.value(),
            'image_size': self.image_size_spin.value(),
            'patience': self.patience_spin.value(),
            'device': self.device_edit.text().strip() or 'cpu',
            'workers': self.workers_spin.value(),
            'extra_args': self.extra_args_edit.text().strip(),
        }
        config['command'] = build_yolov8_train_command(
            data_yaml=config['yaml_path'],
            output_dir=config['output_dir'],
            run_name=config['run_name'],
            model_size=config['model_size'],
            epochs=config['epochs'],
            batch_size=config['batch_size'],
            image_size=config['image_size'],
            patience=config['patience'],
            device=config['device'],
            workers=config['workers'],
            cli_executable=config['cli_executable'],
            extra_args=config['extra_args'],
        )
        return config

    def set_running_state(self, running):
        self._running = bool(running)
        for widget in (
                self.radio_last_export,
                self.radio_existing_yaml,
                self.yaml_path_edit,
                self.yaml_browse_button,
                self.output_dir_edit,
                self.output_browse_button,
                self.run_name_edit,
                self.model_combo,
                self.cli_edit,
                self.epochs_spin,
                self.batch_spin,
                self.image_size_spin,
                self.patience_spin,
                self.device_edit,
                self.workers_spin,
                self.extra_args_edit):
            widget.setEnabled(not self._running)
        self.cancel_button.setEnabled(not self._running)
        self._refresh_command_preview()

    def _refresh_command_preview(self):
        yaml_path = self._selected_yaml()
        try:
            command = build_yolov8_train_command(
                data_yaml=yaml_path,
                output_dir=self.output_dir_edit.text().strip(),
                run_name=self.run_name_edit.text().strip(),
                model_size=self.model_combo.currentText(),
                epochs=self.epochs_spin.value(),
                batch_size=self.batch_spin.value(),
                image_size=self.image_size_spin.value(),
                patience=self.patience_spin.value(),
                device=self.device_edit.text().strip() or 'cpu',
                workers=self.workers_spin.value(),
                cli_executable=self.cli_edit.text().strip() or 'yolo',
                extra_args=self.extra_args_edit.text().strip(),
            )
            self.command_preview.setPlainText(format_command_for_display(command))
            self.start_button.setEnabled(not self._running)
        except TrainingCommandError as exc:
            self.command_preview.setPlainText('Configuration issue: %s' % exc)
            self.start_button.setEnabled(False)

    def _emit_start(self):
        try:
            config = self.current_config()
        except TrainingCommandError as exc:
            QMessageBox.critical(self, 'Train YOLOv8', str(exc))
            return
        self.startRequested.emit(config)


class TrainConfigDialog(QDialog):
    def __init__(self, parent=None, defaults=None):
        super(TrainConfigDialog, self).__init__(parent)
        self.setWindowTitle('Train YOLOv8')
        self.setMinimumSize(760, 720)
        self.setModal(True)
        self.setWindowModality(Qt.ApplicationModal)
        layout = QVBoxLayout(self)
        self.panel = TrainConfigPanel(self, defaults=defaults)
        layout.addWidget(self.panel)
        self.panel.startRequested.connect(self._accept_with_config)
        self.panel.cancelRequested.connect(self.reject)
        self._config = None

    def _accept_with_config(self, config):
        self._config = config
        self.accept()

    def get_config(self):
        return self._config
