#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import codecs
import os.path
import platform
import shutil
import subprocess
import sys
import time
import webbrowser as wb
from functools import partial

try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    # needed for py3+qt4
    # Ref:
    # http://pyqt.sourceforge.net/Docs/PyQt4/incompatible_apis.html
    # http://stackoverflow.com/questions/21217399/pyqt4-qtcore-qvariant-object-instead-of-a-string
    if sys.version_info.major >= 3:
        import sip
        sip.setapi('QVariant', 2)
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

from libs.combobox import ComboBox
from libs.default_label_combobox import DefaultLabelComboBox
from libs.resources import *
from libs.constants import *
from styletheame import THEMES, PALETTES
from libs.utils import *
from libs.settings import Settings
from libs.shape import Shape, DEFAULT_LINE_COLOR, DEFAULT_FILL_COLOR
from libs.stringBundle import StringBundle
from libs.canvas import Canvas
from libs.zoomWidget import ZoomWidget
from libs.lightWidget import LightWidget
from libs.labelDialog import LabelDialog
from libs.colorDialog import ColorDialog
from libs.classification_io import ClassificationIOError, ClassificationSession
from libs.classification_service import ClassificationService
from libs.application_state import ApplicationState
from libs.history_service import HistoryService
from libs.io_adapter import AnnotationIORegistry
from libs.labelFile import LabelFile, LabelFileError, LabelFileFormat
from libs.license_plate_io import (
    LicensePlateDatasetSession,
    LicensePlateIOError,
    ensure_txt_path,
    read_annotations,
    write_annotations,
)
from libs.mode_controller import ModeController
from libs.toolBar import ToolBar
from libs.pascal_voc_io import XML_EXT
from libs.yolo_io import TXT_EXT, YOLODatasetSession, YOLODatasetExportError
from libs.theme_controller import ThemeController
from libs.training_state_service import TrainingStateService
from libs.trainDialog import TrainConfigPanel
from libs.yolo_export_dialog import YOLOExportConfigDialog
from libs.training_runner import (
    format_command_for_display,
    infer_run_artifacts,
    parse_yolov8_progress_line,
)
from libs.create_ml_io import JSON_EXT
from libs.ustr import ustr
from libs.hashableQListWidgetItem import HashableQListWidgetItem

__appname__ = 'Labellix Studio'


def iter_app_icon_candidates():
    """Yield branded icon file paths in priority order."""
    root_dir = os.path.dirname(__file__)
    icons_dir = os.path.abspath(os.path.join(root_dir, 'resources', 'icons'))
    packaging_dir = os.path.join(icons_dir, 'packaging')
    # icon.png at project root is the primary brand icon.
    # Keep only safe sizes to avoid oversized _NET_WM_ICON payloads on X11.
    candidates = [
        os.path.join(root_dir, 'Futuristic glowing square logo design.png'),
        os.path.join(packaging_dir, 'labellix-icon-256.png'),
        os.path.join(packaging_dir, 'labellix-icon-128.png'),
        os.path.join(packaging_dir, 'labellix-icon-64.png'),
        os.path.join(packaging_dir, 'labellix-icon-32.png'),
        os.path.join(icons_dir, 'app.png'),
    ]
    for icon_path in candidates:
        if os.path.exists(icon_path):
            yield icon_path


def get_primary_app_icon_path():
    for icon_path in iter_app_icon_candidates():
        return icon_path
    return None


def _round_pixmap(pix, radius_fraction=0.18):
    """Return a copy of *pix* with rounded corners and a transparent background.

    radius_fraction is the corner radius as a fraction of the shorter side
    (0.18 ≈ the iOS/macOS app-icon squircle look).
    """
    size = pix.size()
    radius = int(min(size.width(), size.height()) * radius_fraction)

    rounded = QPixmap(size)
    rounded.fill(Qt.transparent)

    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

    path = QPainterPath()
    path.addRoundedRect(0, 0, size.width(), size.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pix)
    painter.end()

    return rounded


def build_app_icon():
    """Build a multi-resolution app icon for better dock/taskbar support.

    Futuristic glowing square logo design.png is loaded once, scaled to 256x256 to stay within X11 request
    size limits, rounded corners applied, then smaller sizes are stacked.
    """
    icon = QIcon()
    root_icon = os.path.join(os.path.dirname(__file__), 'Futuristic glowing square logo design.png')
    if os.path.exists(root_icon):
        pix = QPixmap(root_icon)
        if not pix.isNull():
            # Clamp to 256 px to avoid X11 _NET_WM_ICON payload overflow.
            if pix.width() > 256 or pix.height() > 256:
                pix = pix.scaled(256, 256, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon.addPixmap(_round_pixmap(pix))
    for icon_path in iter_app_icon_candidates():
        # Skip Futuristic glowing square logo design.png — already added above at safe size.
        if os.path.basename(icon_path) == 'Futuristic glowing square logo design.png':
            continue
        icon.addFile(icon_path)
    if icon.isNull():
        icon = new_icon('app')
    return icon


def ensure_linux_desktop_entry(icon_path):
    """Create a user-local desktop entry so Linux docks can resolve the app icon."""
    if not sys.platform.startswith('linux') or not icon_path:
        return

    desktop_dir = os.path.expanduser('~/.local/share/applications')
    desktop_file = os.path.join(desktop_dir, 'labellix-studio.desktop')
    script_path = os.path.abspath(__file__)
    desktop_text = (
        '[Desktop Entry]\n'
        'Type=Application\n'
        'Name=Labellix Studio\n'
        'Comment=Image annotation studio\n'
        'Exec=python3 "{script}" %F\n'
        'Icon={icon}\n'
        'Terminal=false\n'
        'Categories=Graphics;Development;\n'
        'StartupNotify=true\n'
        'StartupWMClass=labellix-studio\n'
    ).format(script=script_path, icon=icon_path)

    try:
        if not os.path.isdir(desktop_dir):
            os.makedirs(desktop_dir)
        with codecs.open(desktop_file, 'w', 'utf-8') as f:
            f.write(desktop_text)
    except Exception:
        # Icon fallback still works through setWindowIcon even if desktop entry fails.
        pass


class WindowMixin(object):

    def menu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            add_actions(menu, actions)
        return menu

    def toolbar(self, title, actions=None):
        toolbar = ToolBar(title)
        toolbar.setObjectName(u'%sToolBar' % title)
        # toolbar.setOrientation(Qt.Vertical)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        if actions:
            add_actions(toolbar, actions)
        self.addToolBar(Qt.LeftToolBarArea, toolbar)
        return toolbar


class TrainingWorker(QThread):
    log_line = pyqtSignal(str)
    run_started = pyqtSignal()
    run_finished = pyqtSignal(dict)
    run_failed = pyqtSignal(str)
    run_stopped = pyqtSignal()

    TERMINATE_TIMEOUT_SEC = 3.0
    KILL_TIMEOUT_SEC = 2.0

    def __init__(self, command, parent=None):
        super(TrainingWorker, self).__init__(parent)
        self.command = list(command)
        self._stop_requested = False
        self._process = None

    def stop(self):
        self._stop_requested = True
        if self._process is not None and self._process.poll() is None:
            try:
                self._process.terminate()
            except OSError:
                pass
            try:
                self._process.wait(timeout=self.TERMINATE_TIMEOUT_SEC)
            except subprocess.TimeoutExpired:
                try:
                    self._process.kill()
                except OSError:
                    pass
                try:
                    self._process.wait(timeout=self.KILL_TIMEOUT_SEC)
                except (subprocess.TimeoutExpired, OSError):
                    pass

    def run(self):
        self.run_started.emit()
        try:
            self._process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1)
        except OSError as exc:
            self.run_failed.emit('Could not start training command: %s' % exc)
            return

        stream = self._process.stdout
        try:
            if stream is not None:
                while True:
                    line = stream.readline()
                    if not line:
                        break
                    self.log_line.emit(line.rstrip('\n'))
        finally:
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass

        if self._stop_requested and self._process.poll() is None:
            self.stop()

        return_code = self._process.wait()
        if self._stop_requested:
            self.run_stopped.emit()
            return

        if return_code == 0:
            self.run_finished.emit({'exit_code': return_code})
        else:
            self.run_failed.emit('Training exited with code %d' % return_code)


class MainWindow(QMainWindow, WindowMixin):
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = list(range(3))
    DETECTION_MODE = 'detection'
    CLASSIFICATION_MODE = 'classification'
    LICENSE_PLATE_MODE = 'license_plate'
    SEGMENTATION_MODE = 'segmentation'
    TRAINING_MODE = 'training'
    MODE_STATUS_META = {
        DETECTION_MODE: ('Detection', 'mode_detection', 'labels'),
        CLASSIFICATION_MODE: ('Classification', 'mode_classification', 'expert'),
        LICENSE_PLATE_MODE: ('License Plate', 'mode_detection', 'labels'),
        SEGMENTATION_MODE: ('Segmentation', 'mode_segmentation', 'new'),
        TRAINING_MODE: ('Training', 'neutral', 'save'),
    }

    @property
    def app_mode(self):
        return self.app_state.app_mode

    @app_mode.setter
    def app_mode(self, value):
        self.app_state.app_mode = value

    @property
    def classification_labels(self):
        return self.app_state.classification_labels

    @classification_labels.setter
    def classification_labels(self, value):
        self.app_state.classification_labels = dict(value or {})

    @property
    def training_running(self):
        return self.app_state.training_running

    @training_running.setter
    def training_running(self, value):
        self.app_state.set_training_running(value)

    @property
    def file_path(self):
        return self.app_state.file_path

    @file_path.setter
    def file_path(self, value):
        self.app_state.set_file_path(value)

    @property
    def dir_name(self):
        return self.app_state.dir_name

    @dir_name.setter
    def dir_name(self, value):
        self.app_state.set_directory(value)

    @property
    def m_img_list(self):
        return self.app_state.m_img_list

    @m_img_list.setter
    def m_img_list(self, value):
        self.app_state.set_image_list(value)

    @property
    def cur_img_idx(self):
        return self.app_state.cur_img_idx

    @cur_img_idx.setter
    def cur_img_idx(self, value):
        self.app_state.set_current_index(value)

    @property
    def img_count(self):
        return self.app_state.img_count

    @img_count.setter
    def img_count(self, value):
        self.app_state.img_count = int(value)

    @property
    def dirty(self):
        return self.app_state.dirty

    @dirty.setter
    def dirty(self, value):
        self.app_state.set_dirty(value)

    def __init__(self, default_filename=None, default_prefdef_class_file=None, default_save_dir=None):
        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)
        self.setWindowIcon(build_app_icon())

        # Centralized application state (single source of runtime truth).
        self.app_state = ApplicationState(default_mode=self.DETECTION_MODE)

        # Load setting in the main thread
        self.settings = Settings()
        self.settings.load()
        settings = self.settings
        self.use_modern_icons = bool(settings.get(SETTING_MODERN_ICONS, True))
        self.reduced_motion = bool(settings.get(SETTING_REDUCED_MOTION, False))
        self._ui_animations = []

        self.os_name = platform.system()

        # Load string bundle for i18n
        self.string_bundle = StringBundle.get_bundle()
        def get_str(str_id, fallback=None):
            try:
                return self.string_bundle.get_string(str_id)
            except AssertionError:
                return fallback if fallback is not None else str_id
        self.get_str = get_str

        # Save as Pascal voc xml
        self.default_save_dir = default_save_dir
        self.label_file_format = settings.get(SETTING_LABEL_FILE_FORMAT, LabelFileFormat.PASCAL_VOC)
        # Always start in Detection mode by default.
        self.app_mode = self.DETECTION_MODE
        self.classification_labels = {}
        self.classification_manifest_path = None
        self.classification_export_dir = ustr(settings.get(SETTING_CLASSIFICATION_EXPORT_DIR, ''))
        self.license_plate_export_dir = ustr(settings.get(SETTING_LICENSE_PLATE_EXPORT_DIR, ''))
        self.yolo_export_dir = ustr(settings.get(SETTING_YOLO_EXPORT_DIR, ''))
        self.last_exported_dataset_yaml = ustr(settings.get(SETTING_YOLO_LAST_DATASET_YAML, ''))
        self.training_worker = None
        self.training_running = False
        self._active_training_config = None
        self.training_progress_state = {}

        # For loading all image under a directory
        self.m_img_list = []
        self.dir_name = None
        self.label_hist = []
        self.predefined_classes_file = default_prefdef_class_file
        self.lock_predefined_classes = bool(settings.get(SETTING_LOCK_PREDEFINED_CLASSES, False))
        self.last_open_dir = None
        self.cur_img_idx = 0
        self.img_count = len(self.m_img_list)

        # Whether we need to save or not.
        self.dirty = False

        self._no_selection_slot = False
        self._beginner = True
        self.screencast = "https://youtu.be/p0nR2YsCY_U"

        # Load predefined classes to the list
        self.load_predefined_classes(default_prefdef_class_file)
        self.base_label_hist = list(self.label_hist)

        if self.label_hist:
            self.default_label = self.label_hist[0]
        else:
            predefined_path = ustr(self.predefined_classes_file or '')
            if predefined_path and os.path.exists(predefined_path):
                print('predefined_classes.txt found but no classes loaded: %s' % predefined_path)
            else:
                print('predefined_classes.txt path is missing or invalid: %s' % predefined_path)

        # Main widgets and related state.
        self.label_dialog = LabelDialog(parent=self, list_item=self.label_hist)

        self.items_to_shapes = {}
        self.shapes_to_items = {}
        self.prev_label_text = ''

        list_layout = QVBoxLayout()
        list_layout.setContentsMargins(10, 20, 10, 10)
        list_layout.setSpacing(10)

        # Create a widget for using default label
        self.use_default_label_checkbox = QCheckBox(get_str('useDefaultLabel'))
        self.use_default_label_checkbox.setChecked(False)
        self.default_label_combo_box = DefaultLabelComboBox(self,items=self.label_hist)

        use_default_label_qhbox_layout = QHBoxLayout()
        use_default_label_qhbox_layout.setContentsMargins(0, 0, 0, 0)
        use_default_label_qhbox_layout.setSpacing(8)
        use_default_label_qhbox_layout.addWidget(self.use_default_label_checkbox)
        use_default_label_qhbox_layout.addWidget(self.default_label_combo_box)
        use_default_label_qhbox_layout.setStretch(0, 0)
        use_default_label_qhbox_layout.setStretch(1, 1)
        self.use_default_label_container = QWidget()
        self.use_default_label_container.setLayout(use_default_label_qhbox_layout)

        # Create a widget for edit and diffc button
        self.diffc_button = QCheckBox(get_str('useDifficult'))
        self.diffc_button.setChecked(False)
        self.diffc_button.stateChanged.connect(self.button_state)
        self.lock_predefined_classes_checkbox = QCheckBox(get_str('lockPredefinedClasses', 'Lock predefined classes'))
        self.lock_predefined_classes_checkbox.setChecked(self.lock_predefined_classes)
        self.lock_predefined_classes_checkbox.stateChanged.connect(self.toggle_predefined_classes_lock)
        self.reload_predefined_classes_button = QToolButton()
        self.reload_predefined_classes_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.reload_predefined_classes_button.setIcon(new_icon('open'))
        self.reload_predefined_classes_button.setText(get_str('reloadPredefinedClasses', 'Reload Classes'))
        self.reload_predefined_classes_button.clicked.connect(self.reload_predefined_classes_from_file)
        lock_row_layout = QHBoxLayout()
        lock_row_layout.setContentsMargins(0, 0, 0, 0)
        lock_row_layout.setSpacing(8)
        lock_row_layout.addWidget(self.lock_predefined_classes_checkbox)
        lock_row_layout.addWidget(self.reload_predefined_classes_button)
        lock_row_layout.addStretch(1)
        self.lock_predefined_classes_container = QWidget()
        self.lock_predefined_classes_container.setLayout(lock_row_layout)
        self.edit_button = QToolButton()
        self.edit_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.classification_assign_button = QToolButton()
        self.classification_assign_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.classification_clear_button = QToolButton()
        self.classification_clear_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.classification_export_button = QToolButton()
        self.classification_export_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.classification_current_label = QLabel('')
        self.classification_progress_label = QLabel('')

        classification_buttons_layout = QHBoxLayout()
        classification_buttons_layout.setContentsMargins(0, 0, 0, 0)
        classification_buttons_layout.setSpacing(8)
        classification_buttons_layout.addWidget(self.classification_assign_button)
        classification_buttons_layout.addWidget(self.classification_clear_button)
        classification_buttons_layout.addWidget(self.classification_export_button)
        self.classification_buttons_container = QWidget()
        self.classification_buttons_container.setLayout(classification_buttons_layout)

        # Add some of widgets to list_layout
        list_layout.addWidget(self.edit_button)
        list_layout.addWidget(self.diffc_button)
        list_layout.addWidget(self.lock_predefined_classes_container)
        list_layout.addWidget(self.use_default_label_container)
        list_layout.addWidget(self.classification_current_label)
        list_layout.addWidget(self.classification_progress_label)
        list_layout.addWidget(self.classification_buttons_container)

        # Create and add combobox for showing unique labels in group
        self.combo_box = ComboBox(self)
        self.combo_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        list_layout.addWidget(self.combo_box)

        # Create and add a widget for showing current label items
        self.label_list = QListWidget()
        label_list_container = QWidget()
        label_list_container.setLayout(list_layout)
        self.label_list.itemActivated.connect(self.label_selection_changed)
        self.label_list.itemSelectionChanged.connect(self.label_selection_changed)
        self.label_list.itemDoubleClicked.connect(self.edit_label)
        self.label_list.itemClicked.connect(self.handle_label_list_click)
        # Connect to itemChanged to detect checkbox changes.
        self.label_list.itemChanged.connect(self.label_item_changed)
        list_layout.addWidget(self.label_list)



        self.dock = QDockWidget(get_str('boxLabelText'), self)
        self.dock.setObjectName('labelsDock')
        self.dock.setWidget(label_list_container)

        self.file_list_widget = QListWidget()
        self.file_list_widget.itemDoubleClicked.connect(self.file_item_double_clicked)
        file_list_layout = QVBoxLayout()
        file_list_layout.setContentsMargins(10, 12, 10, 10)
        file_list_layout.setSpacing(8)
        file_list_layout.addWidget(self.file_list_widget)
        file_list_container = QWidget()
        file_list_container.setLayout(file_list_layout)
        self.file_dock = QDockWidget(get_str('fileList'), self)
        self.file_dock.setObjectName('filesDock')
        self.file_dock.setWidget(file_list_container)

        self.training_config_panel = TrainConfigPanel(self)
        self.training_config_panel.startRequested.connect(self.start_training_from_panel)
        self.training_config_panel.cancelRequested.connect(self.exit_training_mode)

        self.training_log_text = QPlainTextEdit()
        self.training_log_text.setReadOnly(True)
        self.training_log_text.setMaximumBlockCount(8000)
        self.training_log_text.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.training_summary_label = QLabel('Run Summary: -')
        self.training_summary_label.setWordWrap(True)
        self.training_summary_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.training_status_label = QLabel('Status: Idle')
        self.training_epoch_label = QLabel('Epoch: -')
        self.training_eta_label = QLabel('ETA: -')
        self.training_metrics_label = QLabel('Metrics: -')
        self.training_progress_bar = QProgressBar()
        self.training_progress_bar.setRange(0, 100)
        self.training_progress_bar.setValue(0)
        self.training_progress_bar.setFormat('Training progress: %p%')
        training_buttons_layout = QHBoxLayout()
        training_buttons_layout.setContentsMargins(0, 0, 0, 0)
        training_buttons_layout.setSpacing(8)
        self.training_clear_button = QPushButton('Clear Logs')
        self.training_clear_button.setObjectName('trainingSecondaryButton')
        self.training_clear_button.setIcon(new_icon('delete'))
        self.training_save_button = QPushButton('Save Logs')
        self.training_save_button.setObjectName('trainingPrimaryButton')
        self.training_save_button.setIcon(new_icon('save'))
        training_buttons_layout.addWidget(self.training_clear_button)
        training_buttons_layout.addWidget(self.training_save_button)
        training_buttons_layout.addStretch(1)

        training_layout = QVBoxLayout()
        training_layout.setContentsMargins(10, 12, 10, 10)
        training_layout.setSpacing(8)
        training_layout.addWidget(self.training_summary_label)
        training_layout.addWidget(self.training_status_label)
        training_layout.addWidget(self.training_epoch_label)
        training_layout.addWidget(self.training_eta_label)
        training_layout.addWidget(self.training_metrics_label)
        training_layout.addWidget(self.training_progress_bar)
        training_layout.addLayout(training_buttons_layout)
        training_layout.addWidget(self.training_log_text)
        training_container = QWidget()
        training_container.setLayout(training_layout)
        self.training_log_dock = QDockWidget(get_str('trainingLogs', 'Training Logs'), self)
        self.training_log_dock.setObjectName('trainingLogs')
        self.training_log_dock.setWidget(training_container)

        self.zoom_widget = ZoomWidget()
        self.light_widget = LightWidget(get_str('lightWidgetTitle'))
        self.color_dialog = ColorDialog(parent=self)

        self.canvas = Canvas(parent=self)
        self.canvas.zoomRequest.connect(self.zoom_request)
        self.canvas.lightRequest.connect(self.light_request)
        # Default to free rectangle drawing (non-square) on startup.
        self.canvas.set_drawing_shape_to_square(False)

        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(True)
        self.scroll_bars = {
            Qt.Vertical: scroll.verticalScrollBar(),
            Qt.Horizontal: scroll.horizontalScrollBar()
        }
        self.scroll_area = scroll
        self.canvas.scrollRequest.connect(self.scroll_request)

        self.canvas.newShape.connect(self.new_shape)
        self.canvas.shapeMoved.connect(self.on_canvas_shape_moved)
        self.canvas.selectionChanged.connect(self.shape_selection_changed)
        self.canvas.drawingPolygon.connect(self.toggle_drawing_sensitive)

        self.central_stack = QStackedWidget()
        self.central_stack.addWidget(scroll)                      # index 0 — labeling canvas
        self.central_stack.addWidget(self.training_config_panel)  # index 1 — training setup
        self.setCentralWidget(self.central_stack)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.file_dock)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.training_log_dock)
        self.dock.visibilityChanged.connect(lambda visible: self._on_dock_visibility_changed(self.dock, visible))
        self.file_dock.visibilityChanged.connect(lambda visible: self._on_dock_visibility_changed(self.file_dock, visible))
        self.training_log_dock.visibilityChanged.connect(lambda visible: self._on_dock_visibility_changed(self.training_log_dock, visible))
        self.file_dock.setFeatures(QDockWidget.DockWidgetFloatable)
        self.training_log_dock.setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable)
        self.training_log_dock.hide()
        self.training_clear_button.clicked.connect(self.training_log_text.clear)
        self.training_save_button.clicked.connect(self.save_training_logs)

        self.dock_features = QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetFloatable
        self.dock.setFeatures(self.dock.features() ^ self.dock_features)

        # Actions
        action = partial(new_action, self)
        quit = action(get_str('quit'), self.close,
                      'Ctrl+Q', 'quit', get_str('quitApp'))

        open = action(get_str('openFile'), self.open_file,
                      'Ctrl+O', 'open', get_str('openFileDetail'))

        open_dir = action(get_str('openDir'), self.open_dir_dialog,
                          'Ctrl+u', 'open', get_str('openDir'))

        change_save_dir = action(get_str('changeSaveDir'), self.change_save_dir_dialog,
                                 'Ctrl+r', 'open', get_str('changeSavedAnnotationDir'))

        open_annotation = action(get_str('openAnnotation'), self.open_annotation_dialog,
                                 'Ctrl+Shift+O', 'open', get_str('openAnnotationDetail'))
        copy_prev_bounding = action(get_str('copyPrevBounding'), self.copy_previous_bounding_boxes, 'Ctrl+v', 'copy', get_str('copyPrevBounding'))

        open_next_image = action(get_str('nextImg'), self.open_next_image,
                     ['d', 'Right', 'PgDown'], 'next', get_str('nextImgDetail'))
        open_next_image.setShortcutContext(Qt.ApplicationShortcut)

        open_prev_image = action(get_str('prevImg'), self.open_prev_image,
                     ['a', 'Left', 'PgUp'], 'prev', get_str('prevImgDetail'))
        open_prev_image.setShortcutContext(Qt.ApplicationShortcut)

        verify = action(get_str('verifyImg'), self.verify_image,
                        'space', 'verify', get_str('verifyImgDetail'))

        save = action(get_str('save'), self.save_file,
                      'Ctrl+S', 'save', get_str('saveDetail'), enabled=False)

        def get_format_meta(format):
            """
            returns a tuple containing (title, icon_name) of the selected format
            """
            if format == LabelFileFormat.PASCAL_VOC:
                return '&PascalVOC', 'format_voc'
            elif format == LabelFileFormat.YOLO:
                return '&YOLO', 'format_yolo'
            elif format == LabelFileFormat.CREATE_ML:
                return '&CreateML', 'format_createml'

        save_format = action(get_format_meta(self.label_file_format)[0],
                             self.change_format, 'Ctrl+Y',
                             get_format_meta(self.label_file_format)[1],
                             get_str('changeSaveFormat'), enabled=True)

        save_as = action(get_str('saveAs'), self.save_file_as,
                         'Ctrl+Shift+S', 'save-as', get_str('saveAsDetail'), enabled=False)

        close = action(get_str('closeCur'), self.close_file, 'Ctrl+W', 'close', get_str('closeCurDetail'))

        delete_image = action(get_str('deleteImg'), self.delete_image, 'Ctrl+Shift+X', 'close', get_str('deleteImgDetail'))

        reset_all = action(get_str('resetAll'), self.reset_all, None, 'resetall', get_str('resetAllDetail'))

        color1 = action(get_str('boxLineColor'), self.choose_color1,
                        'Ctrl+L', 'color_line', get_str('boxLineColorDetail'))

        create_mode = action(get_str('crtBox'), self.set_create_mode,
                             'w', 'new', get_str('crtBoxDetail'), enabled=False)
        edit_mode = action(get_str('editBox'), self.set_edit_mode,
                           'Ctrl+J', 'edit', get_str('editBoxDetail'), enabled=False)

        create = action(get_str('crtBox'), self.create_shape,
                        'w', 'new', get_str('crtBoxDetail'), enabled=False)
        delete = action(get_str('delBox'), self.delete_selected_shape,
                        'Delete', 'delete', get_str('delBoxDetail'), enabled=False)
        copy = action(get_str('dupBox'), self.copy_selected_shape,
                      'Ctrl+D', 'copy', get_str('dupBoxDetail'),
                      enabled=False)
        undo = action('Undo', self.undo_annotation_change,
                  'Ctrl+Z', 'undo', 'Undo last annotation change', enabled=False)
        redo = action('Redo', self.redo_annotation_change,
                  'Ctrl+Shift+Z', 'redo', 'Redo last undone annotation change', enabled=False)

        advanced_mode = action(get_str('advancedMode'), self.toggle_advanced_mode,
                               'Ctrl+Shift+A', 'expert', get_str('advancedModeDetail'),
                               checkable=True)
        detection_mode = action('Detection Mode', self.toggle_detection_mode,
                 'Ctrl+Shift+D', 'expert', 'Switch to detection bounding-box labeling mode',
                 checkable=True)
        classification_mode = action(get_str('classificationMode'), self.toggle_classification_mode,
                         'Ctrl+Shift+C', 'expert', get_str('classificationModeDetail'),
                         checkable=True)
        license_plate_mode = action(get_str('licensePlateMode', 'License Plate Mode'), self.toggle_license_plate_mode,
                 'Ctrl+Shift+N', 'expert', get_str('licensePlateModeDetail', 'Switch to license plate annotation mode'),
                 checkable=True)
        segmentation_mode = action('Segmentation Mode', self.toggle_segmentation_mode,
                 'Ctrl+Shift+G', 'expert', 'Enable polygon segmentation labeling mode',
                 checkable=True)
        training_mode = action('Training Mode', self.toggle_training_mode,
                 'Ctrl+Shift+K', 'expert', 'Switch to YOLO training setup mode',
                 checkable=True)
        mode_shortcuts = action(
            get_str('modeShortcuts', 'Mode Shortcuts'),
            self.show_mode_shortcuts_dialog,
            None,
            'help',
            get_str('modeShortcutsDetail', 'Show mode switching shortcuts'))
        assign_class = action(get_str('assignClass'), self.assign_classification_label,
                      'c', 'edit', get_str('assignClassDetail'), enabled=False)
        clear_class = action(get_str('clearClass'), self.clear_classification_label,
                     None, 'delete', get_str('clearClassDetail'), enabled=False)
        export_classes = action(get_str('exportClasses'), self.export_classification_dataset,
                    'Ctrl+Shift+E', 'save', get_str('exportClassesDetail'), enabled=False)
        export_license_plate_dataset = action(
            get_str('exportLicensePlateDataset', 'Export License Plate Dataset'),
            self.export_license_plate_dataset,
            None,
            'save',
            get_str('exportLicensePlateDatasetDetail', 'Copy or move labeled image/txt pairs into a dataset folder'),
            enabled=False)
        export_yolo_dataset = action(get_str('exportYOLODataset', 'Export YOLO Dataset'), self.export_yolo_dataset,
            'Ctrl+Shift+T', 'save', get_str('exportYOLODatasetDetail', 'Create train/test/valid YOLO dataset folders'), enabled=False)
        train_yolov8 = action(get_str('trainYOLOv8', 'Train YOLOv8'), lambda _checked=False: self.toggle_training_mode(True),
            None, 'save', get_str('trainYOLOv8Detail', 'Start YOLOv8 training from dataset.yaml'), enabled=True)

        for mode_action in (detection_mode, classification_mode, license_plate_mode, segmentation_mode, training_mode):
            mode_action.setShortcutContext(Qt.ApplicationShortcut)
        stop_training = action(get_str('stopTraining', 'Stop Training'), self.stop_training_process,
            None, 'cancel', get_str('stopTrainingDetail', 'Stop the active training process'), enabled=False)
        next_unlabeled = action(get_str('nextUnlabeled'), self.open_next_unlabeled_image,
                    'n', 'next', get_str('nextUnlabeledDetail'), enabled=False)

        hide_all = action(get_str('hideAllBox'), partial(self.toggle_polygons, False),
                          'Ctrl+H', 'hide', get_str('hideAllBoxDetail'),
                          enabled=False)
        show_all = action(get_str('showAllBox'), partial(self.toggle_polygons, True),
                          'Ctrl+A', 'hide', get_str('showAllBoxDetail'),
                          enabled=False)

        help_default = action(get_str('tutorialDefault'), self.show_default_tutorial_dialog, None, 'help', get_str('tutorialDetail'))
        show_info = action(get_str('info'), self.show_info_dialog, None, 'help', get_str('info'))
        show_shortcut = action(get_str('shortcut'), self.show_shortcuts_dialog, '?', 'help', get_str('shortcut'))
        show_shortcut.setShortcutContext(Qt.ApplicationShortcut)

        zoom = QWidgetAction(self)
        zoom.setDefaultWidget(self.zoom_widget)
        self.zoom_widget.setWhatsThis(
            u"Zoom in or out of the image. Also accessible with"
            " %s and %s from the canvas." % (format_shortcut("Ctrl+[-+]"),
                                             format_shortcut("Ctrl+Wheel")))
        self.zoom_widget.setEnabled(False)

        zoom_in = action(get_str('zoomin'), partial(self.add_zoom, 10),
                         'Ctrl++', 'zoom-in', get_str('zoominDetail'), enabled=False)
        zoom_out = action(get_str('zoomout'), partial(self.add_zoom, -10),
                          'Ctrl+-', 'zoom-out', get_str('zoomoutDetail'), enabled=False)
        zoom_org = action(get_str('originalsize'), partial(self.set_zoom, 100),
                          'Ctrl+=', 'zoom', get_str('originalsizeDetail'), enabled=False)
        fit_window = action(get_str('fitWin'), self.set_fit_window,
                            'Ctrl+F', 'fit-window', get_str('fitWinDetail'),
                            checkable=True, enabled=False)
        fit_width = action(get_str('fitWidth'), self.set_fit_width,
                           'Ctrl+Shift+F', 'fit-width', get_str('fitWidthDetail'),
                           checkable=True, enabled=False)
        # Group zoom controls into a list for easier toggling.
        zoom_actions = (self.zoom_widget, zoom_in, zoom_out,
                        zoom_org, fit_window, fit_width)
        self.zoom_mode = self.MANUAL_ZOOM
        self.scalers = {
            self.FIT_WINDOW: self.scale_fit_window,
            self.FIT_WIDTH: self.scale_fit_width,
            # Set to one to scale to 100% when loading files.
            self.MANUAL_ZOOM: lambda: 1,
        }

        light = QWidgetAction(self)
        light.setDefaultWidget(self.light_widget)
        self.light_widget.setWhatsThis(
            u"Brighten or darken current image. Also accessible with"
            " %s and %s from the canvas." % (format_shortcut("Ctrl+Shift+[-+]"),
                                             format_shortcut("Ctrl+Shift+Wheel")))
        self.light_widget.setEnabled(False)

        light_brighten = action(get_str('lightbrighten'), partial(self.add_light, 10),
                                'Ctrl+Shift++', 'light_lighten', get_str('lightbrightenDetail'), enabled=False)
        light_darken = action(get_str('lightdarken'), partial(self.add_light, -10),
                              'Ctrl+Shift+-', 'light_darken', get_str('lightdarkenDetail'), enabled=False)
        light_org = action(get_str('lightreset'), partial(self.set_light, 50),
                           'Ctrl+Shift+=', 'light_reset', get_str('lightresetDetail'), checkable=True, enabled=False)
        light_org.setChecked(True)

        # Group light controls into a list for easier toggling.
        light_actions = (self.light_widget, light_brighten,
                         light_darken, light_org)

        edit = action(get_str('editLabel'), self.edit_label,
                      'Ctrl+E', 'edit', get_str('editLabelDetail'),
                      enabled=False)
        self.edit_button.setDefaultAction(edit)
        self.classification_assign_button.setDefaultAction(assign_class)
        self.classification_clear_button.setDefaultAction(clear_class)
        self.classification_export_button.setDefaultAction(export_classes)

        shape_line_color = action(get_str('shapeLineColor'), self.choose_shape_line_color,
                                  icon='color_line', tip=get_str('shapeLineColorDetail'),
                                  enabled=False)
        shape_fill_color = action(get_str('shapeFillColor'), self.choose_shape_fill_color,
                                  icon='color', tip=get_str('shapeFillColorDetail'),
                                  enabled=False)

        labels = self.dock.toggleViewAction()
        labels.setText(get_str('showHide'))
        labels.setShortcut('Ctrl+Shift+L')

        # Label list context menu.
        label_menu = QMenu()
        add_actions(label_menu, (edit, delete))
        self.label_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.label_list.customContextMenuRequested.connect(
            self.pop_label_list_menu)

        # Draw squares/rectangles
        self.draw_squares_option = QAction(get_str('drawSquares'), self)
        self.draw_squares_option.setShortcut('Ctrl+Shift+R')
        self.draw_squares_option.setCheckable(True)
        self.draw_squares_option.setChecked(False)
        self.draw_squares_option.triggered.connect(self.toggle_draw_square)

        self.compact_mode_option = QAction('Compact Mode', self)
        self.compact_mode_option.setShortcut('Ctrl+Shift+M')
        self.compact_mode_option.setCheckable(True)
        self.compact_mode_option.setChecked(settings.get(SETTING_COMPACT_MODE, False))
        self.compact_mode_option.triggered.connect(self.toggle_compact_mode)

        self.modern_icons_option = QAction('Modern Icons', self)
        self.modern_icons_option.setCheckable(True)
        self.modern_icons_option.setChecked(self.use_modern_icons)
        self.modern_icons_option.triggered.connect(self.toggle_modern_icons)

        self.reduced_motion_option = QAction('Reduced Motion', self)
        self.reduced_motion_option.setCheckable(True)
        self.reduced_motion_option.setChecked(self.reduced_motion)
        self.reduced_motion_option.triggered.connect(self.toggle_reduced_motion)

        self.ui_preferences_preview_action = QAction('Preview UI Preferences', self)
        self.ui_preferences_preview_action.triggered.connect(self.show_ui_preferences_preview)

        self.focus_mode_option = QAction('Focus Mode', self)
        self.focus_mode_option.setShortcut('F11')
        self.focus_mode_option.setShortcutContext(Qt.ApplicationShortcut)
        self.focus_mode_option.setCheckable(True)
        self.focus_mode_option.setChecked(settings.get(SETTING_FOCUS_MODE, False))
        self.focus_mode_option.triggered.connect(self.toggle_focus_mode)
        self._focus_mode_restore_state = None
        self.exit_focus_mode_action = QAction('Exit Focus Mode', self)
        self.exit_focus_mode_action.setShortcut('Esc')
        self.exit_focus_mode_action.setShortcutContext(Qt.ApplicationShortcut)
        self.exit_focus_mode_action.triggered.connect(self.exit_focus_mode)
        self.addAction(self.exit_focus_mode_action)

        # Store actions for further handling.
        self.actions = Struct(save=save, save_format=save_format, saveAs=save_as, open=open, close=close, resetAll=reset_all, deleteImg=delete_image,
                  verify=verify, lineColor=color1, create=create, delete=delete, edit=edit, copy=copy, undo=undo, redo=redo,
                      nextImage=open_next_image, prevImage=open_prev_image,
                              createMode=create_mode, editMode=edit_mode, advancedMode=advanced_mode,
                              detectionMode=detection_mode, classificationMode=classification_mode, assignClass=assign_class, clearClass=clear_class,
                              licensePlateMode=license_plate_mode,
                              segmentationMode=segmentation_mode, trainingMode=training_mode,
                              exportClasses=export_classes, exportLicensePlateDataset=export_license_plate_dataset, exportYOLODataset=export_yolo_dataset,
                              trainYOLOv8=train_yolov8, stopTraining=stop_training, nextUnlabeled=next_unlabeled,
                              shapeLineColor=shape_line_color, shapeFillColor=shape_fill_color,
                              zoom=zoom, zoomIn=zoom_in, zoomOut=zoom_out, zoomOrg=zoom_org,
                              fitWindow=fit_window, fitWidth=fit_width,
                              zoomActions=zoom_actions,
                              lightBrighten=light_brighten, lightDarken=light_darken, lightOrg=light_org,
                              lightActions=light_actions,
                              fileMenuActions=(
                                  open, open_dir, save, save_as, close, reset_all, quit),
                              beginner=(), advanced=(), segmentation=(), classification=(), training=(), classificationMenu=(), classificationContext=(), trainingMenu=(), trainingContext=(),
                              editMenu=(undo, redo, None, edit, copy, delete,
                                        None, color1, self.draw_squares_option),
                              beginnerContext=(create, edit, copy, delete),
                              advancedContext=(create_mode, edit_mode, edit, copy,
                                               delete, shape_line_color, shape_fill_color),
                              segmentationContext=(create_mode, edit_mode, edit, copy,
                                               delete, shape_line_color, shape_fill_color),
                              onLoadActive=(
                                  close, create, create_mode, edit_mode),
                              onShapesPresent=(save_as, hide_all, show_all))

        self.menus = Struct(
            file=self.menu(get_str('menu_file')),
            edit=self.menu(get_str('menu_edit')),
            mode=self.menu('Mode'),
            train=self.menu(get_str('menu_train', 'Train')),
            export=self.menu(get_str('menu_export', 'Export')),
            view=self.menu(get_str('menu_view')),
            theme=self.menu('Theme'),
            help=self.menu(get_str('menu_help')),
            recentFiles=QMenu(get_str('menu_openRecent')),
            uiPreferences=QMenu('UI Preferences'),
            labelList=label_menu)

        default_theme = DEFAULT_THEME if DEFAULT_THEME in THEMES else 'light'
        self.theme_controller = ThemeController(self, THEMES, PALETTES, default_theme=default_theme)
        self.current_theme = self.theme_controller.current_theme

        # Auto saving : Enable auto saving if pressing next
        self.auto_saving = QAction(get_str('autoSaveMode'), self)
        self.auto_saving.setCheckable(True)
        self.auto_saving.setChecked(settings.get(SETTING_AUTO_SAVE, False))
        self.auto_saving.triggered.connect(lambda _checked=False: self.update_status_chips())
        self.auto_next_on_save = QAction(get_str('autoNextOnSave', 'Auto Next on Save'), self)
        self.auto_next_on_save.setCheckable(True)
        self.auto_next_on_save.setChecked(settings.get(SETTING_AUTO_NEXT_ON_SAVE, False))
        self.auto_next_on_save.triggered.connect(lambda _checked=False: self.update_status_chips())
        # Sync single class mode from PR#106
        self.single_class_mode = QAction(get_str('singleClsMode'), self)
        self.single_class_mode.setShortcut("Ctrl+Shift+S")
        self.single_class_mode.setCheckable(True)
        self.single_class_mode.setChecked(settings.get(SETTING_SINGLE_CLASS, False))
        self.lastLabel = None
        # Add option to enable/disable labels being displayed at the top of bounding boxes
        self.display_label_option = QAction(get_str('displayLabel'), self)
        self.display_label_option.setShortcut("Ctrl+Shift+P")
        self.display_label_option.setCheckable(True)
        self.display_label_option.setChecked(settings.get(SETTING_PAINT_LABEL, False))
        self.display_label_option.triggered.connect(self.toggle_paint_labels_option)

        add_actions(self.menus.file,
                    (open, open_dir, change_save_dir, open_annotation, copy_prev_bounding, self.menus.recentFiles,
                     save, save_format, save_as, export_license_plate_dataset, export_yolo_dataset, train_yolov8, close, reset_all, delete_image, quit))
        add_actions(self.menus.train, (train_yolov8, stop_training))
        add_actions(self.menus.export, (export_license_plate_dataset, export_yolo_dataset, export_classes))
        add_actions(self.menus.mode, (
            detection_mode,
            classification_mode,
            license_plate_mode,
            segmentation_mode,
            training_mode,
            None,
            mode_shortcuts,
            advanced_mode,
        ))
        add_actions(self.menus.help, (help_default, show_info, show_shortcut))

        # Theme menu (top-level)
        self._theme_actions = self.theme_controller.setup_theme_menu(self.menus.theme)

        add_actions(self.menus.uiPreferences, (
            self.ui_preferences_preview_action,
            None,
            self.compact_mode_option,
            self.focus_mode_option,
            self.modern_icons_option,
            self.reduced_motion_option,
        ))

        add_actions(self.menus.view, (
            self.auto_saving,
            self.auto_next_on_save,
            self.single_class_mode,
            self.display_label_option,
            self.menus.uiPreferences,
            None,
            labels, None,
            hide_all, show_all, None,
            zoom_in, zoom_out, zoom_org, None,
            fit_window, fit_width, None,
            light_brighten, light_darken, light_org))

        self.menus.file.aboutToShow.connect(self.update_file_menu)

        # Custom context menu for the canvas widget:
        add_actions(self.canvas.menus[0], self.actions.beginnerContext)
        add_actions(self.canvas.menus[1], (
            action('&Copy here', self.copy_shape),
            action('&Move here', self.move_shape)))

        self.tools = self.toolbar('Tools')
        self.actions.beginner = (
            open, open_dir, change_save_dir, open_next_image, open_prev_image, verify, save, save_format, None,
            undo, redo, None, create, copy, delete, None,
            train_yolov8, stop_training, None,
            zoom_in, zoom, zoom_out, fit_window, fit_width, None,
            light_brighten, light, light_darken, light_org)

        self.actions.advanced = (
            open, open_dir, change_save_dir, open_next_image, open_prev_image, verify, save, save_format, None,
            undo, redo, None,
            create, copy, delete, None,
            train_yolov8, stop_training, None,
            create_mode, edit_mode, None,
            hide_all, show_all)
        self.actions.segmentation = (
            open, open_dir, change_save_dir, open_next_image, open_prev_image, verify, save, save_format, None,
            undo, redo, None,
            create_mode, edit_mode, copy, delete, None,
            train_yolov8, stop_training, None,
            hide_all, show_all, None,
            zoom_in, zoom, zoom_out, fit_window, fit_width, None,
            light_brighten, light, light_darken, light_org)
        self.actions.classification = (
            open, open_dir, open_next_image, open_prev_image, next_unlabeled, save, None,
            assign_class, clear_class, export_classes, None,
            zoom_in, zoom, zoom_out, fit_window, fit_width, None,
            light_brighten, light, light_darken, light_org)
        self.actions.training = (
            train_yolov8, stop_training, None,
            open, open_dir, save, export_yolo_dataset)
        self.actions.trainingMenu = (stop_training,)
        self.actions.classificationMenu = (
            assign_class, clear_class, next_unlabeled, None, export_classes)

        self.statusBar().showMessage('%s started.' % __appname__)
        self.statusBar().show()

        # Application state.
        self.image = QImage()
        self.file_path = ustr(default_filename)
        self.last_open_dir = None
        self.recent_files = []
        self.max_recent = 7
        self.line_color = None
        self.fill_color = None
        self.zoom_level = 100
        self.fit_window = False
        # Add Chris
        self.difficult = False

        # Annotation history for undo/redo in detection and segmentation modes.
        self.history_service = HistoryService(self, max_entries=100, checkpoint_interval_ms=250)
        self.history_service.timer.timeout.connect(self._record_history_checkpoint)

        # Fix the compatible issue for qt4 and qt5. Convert the QStringList to python list
        if settings.get(SETTING_RECENT_FILES):
            if have_qstring():
                recent_file_qstring_list = settings.get(SETTING_RECENT_FILES)
                self.recent_files = [ustr(i) for i in recent_file_qstring_list]
            else:
                self.recent_files = recent_file_qstring_list = settings.get(SETTING_RECENT_FILES)

        size = settings.get(SETTING_WIN_SIZE, QSize(600, 500))
        position = QPoint(0, 0)
        saved_position = settings.get(SETTING_WIN_POSE, position)
        # Fix the multiple monitors issue
        for i in range(QApplication.desktop().screenCount()):
            if QApplication.desktop().availableGeometry(i).contains(saved_position):
                position = saved_position
                break
        self.resize(size)
        self.move(position)
        save_dir = ustr(settings.get(SETTING_SAVE_DIR, None))
        self.last_open_dir = ustr(settings.get(SETTING_LAST_OPEN_DIR, None))
        if self.default_save_dir is None and save_dir is not None and os.path.exists(save_dir):
            self.default_save_dir = save_dir
            self.statusBar().showMessage('%s started. Annotation will be saved to %s' %
                                         (__appname__, self.default_save_dir))
            self.statusBar().show()

        self.restoreState(settings.get(SETTING_WIN_STATE, QByteArray()))
        Shape.line_color = self.line_color = QColor(settings.get(SETTING_LINE_COLOR, DEFAULT_LINE_COLOR))
        Shape.fill_color = self.fill_color = QColor(settings.get(SETTING_FILL_COLOR, DEFAULT_FILL_COLOR))
        self.canvas.set_drawing_color(self.line_color)
        # Add chris
        Shape.difficult = self.difficult

        def xbool(x):
            if isinstance(x, QVariant):
                return x.toBool()
            return bool(x)

        if xbool(settings.get(SETTING_ADVANCE_MODE, False)):
            self.actions.advancedMode.setChecked(True)
            self.toggle_advanced_mode()

        # Populate the File menu dynamically.
        self.update_file_menu()

        # Since loading the file may take some time, make sure it runs in the background.
        if self.file_path and os.path.isdir(self.file_path):
            self.queue_event(partial(self.import_dir_images, self.file_path or ""))
        elif self.file_path and self.last_open_dir and os.path.isdir(self.last_open_dir):
            # Resume full browsing session: restore directory list then focus last image.
            self.queue_event(partial(self.import_dir_images, self.last_open_dir))
            self.queue_event(partial(self.load_file, self.file_path))
        elif self.file_path:
            self.queue_event(partial(self.load_file, self.file_path or ""))

        # Callbacks:
        self.zoom_widget.valueChanged.connect(self.paint_canvas)
        self.light_widget.valueChanged.connect(self.paint_canvas)

        self.mode_controller = ModeController(self)
        self.classification_service = ClassificationService()
        self.training_state_service = TrainingStateService()
        self.annotation_io = AnnotationIORegistry()

        self.populate_mode_actions()
        self.toggle_classification_mode(self.app_mode == self.CLASSIFICATION_MODE)
        self.toggle_license_plate_mode(self.app_mode == self.LICENSE_PLATE_MODE)
        self.toggle_segmentation_mode(self.app_mode == self.SEGMENTATION_MODE)

        # Display cursor coordinates at the right of status bar
        self.mode_status_label = QToolButton()
        self.mode_status_label.setObjectName('modeChip')
        self.format_status_label = QToolButton()
        self.format_status_label.setObjectName('formatChip')
        self.autosave_status_label = QToolButton()
        self.autosave_status_label.setObjectName('autosaveChip')
        self.image_counter_label = QToolButton()
        self.image_counter_label.setObjectName('counterChip')
        self.shortcut_hints_label = QLabel('')
        self.label_coordinates = QLabel('')
        for chip in (self.mode_status_label, self.format_status_label, self.autosave_status_label, self.image_counter_label):
            chip.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            chip.setAutoRaise(True)
            chip.setEnabled(False)
            chip.setIconSize(QSize(14, 14))
            chip.setCursor(Qt.ArrowCursor)
        self.statusBar().addPermanentWidget(self.mode_status_label)
        self.statusBar().addPermanentWidget(self.format_status_label)
        self.statusBar().addPermanentWidget(self.autosave_status_label)
        self.statusBar().addPermanentWidget(self.image_counter_label)
        self.statusBar().addPermanentWidget(self.shortcut_hints_label, 1)
        self.statusBar().addPermanentWidget(self.label_coordinates)

        self._mode_glow_phase = 0.0
        self._mode_glow_timer = QTimer(self)
        self._mode_glow_timer.setInterval(120)
        self._mode_glow_timer.timeout.connect(self._animate_mode_chip)
        if not self.reduced_motion:
            self._mode_glow_timer.start()

        self.current_theme = self.theme_controller.current_theme
        self._apply_modern_ui()
        self.refresh_ui_icons()
        self.update_status_chips()
        self.update_shortcut_hints()
        self.update_history_actions()
        resume_zoom = settings.get(SETTING_RESUME_ZOOM, None)
        if resume_zoom:
            self.set_zoom(int(resume_zoom))
        if self.focus_mode_option.isChecked():
            self.toggle_focus_mode(True)

        # Open Dir if default file
        if self.file_path and os.path.isdir(self.file_path):
            self.open_dir_dialog(dir_path=self.file_path, silent=True)

    def apply_theme(self, theme_name, action_list=None):
        """Switch the application theme at runtime."""
        self.theme_controller.apply_theme(theme_name, action_list)
        self.current_theme = self.theme_controller.current_theme

    def _motion_profile(self):
        return self.theme_controller.motion_profile()

    def _sync_motion_profile(self):
        self.theme_controller.sync_motion_profile()
            
    def _apply_modern_ui(self):
        self.theme_controller.apply_modern_ui()
        self.current_theme = self.theme_controller.current_theme

    def _animate_widget_fade_in(self, widget, duration=170):
        if self.reduced_motion or widget is None:
            return
        profile = self._motion_profile()
        duration = profile.get('dock_fade_ms', duration) if duration is None else duration
        if duration <= 0:
            return
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b'opacity', widget)
        animation.setDuration(duration)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(profile.get('easing', QEasingCurve.OutCubic))
        self._ui_animations.append(animation)
        animation.finished.connect(lambda: self._ui_animations.remove(animation) if animation in self._ui_animations else None)
        animation.finished.connect(lambda: widget.setGraphicsEffect(None))
        animation.start()

    def _on_dock_visibility_changed(self, dock, visible):
        if visible:
            delay_map = {
                'labelsDock': 0,
                'filesDock': 35,
                'trainingLogs': 70,
            }
            delay = delay_map.get(dock.objectName(), 0)
            duration = self._motion_profile().get('dock_fade_ms', 150)
            if self.reduced_motion or delay <= 0:
                self._animate_widget_fade_in(dock, duration)
            else:
                QTimer.singleShot(delay, lambda: self._animate_widget_fade_in(dock, duration))

    def _chip_palette(self):
        return self.theme_controller.chip_palette()

    def _set_chip_style(self, label, bg, fg, border):
        self.theme_controller.set_chip_style(label, bg, fg, border)

    def _current_mode_key(self):
        if self.is_classification_mode():
            return 'mode_classification'
        if self.is_segmentation_mode():
            return 'mode_segmentation'
        if self.is_training_mode():
            return 'neutral'
        return 'mode_detection'

    def _animate_mode_chip(self):
        self.theme_controller.animate_mode_chip()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.canvas.set_drawing_shape_to_square(self.draw_squares_option.isChecked())

    def keyPressEvent(self, event):
        if self._handle_numeric_class_shortcut(event):
            event.accept()
            return

        if event.key() == Qt.Key_Control:
            # Hold Ctrl to force square drawing temporarily.
            self.canvas.set_drawing_shape_to_square(True)
            event.accept()
            return

        super(MainWindow, self).keyPressEvent(event)

    def _available_numeric_shortcut_labels(self):
        labels = [trimmed(label) for label in self.label_hist if trimmed(label)]
        return labels[:9]

    def _shortcut_index_from_key_event(self, event):
        key = event.key()
        if Qt.Key_1 <= key <= Qt.Key_9:
            return key - Qt.Key_1
        return None

    def _numeric_shortcuts_enabled_for_focus(self):
        focus_widget = QApplication.focusWidget()
        blocked_types = (QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox)
        return not isinstance(focus_widget, blocked_types)

    def _handle_numeric_class_shortcut(self, event):
        if self.image.isNull():
            return False

        modifiers = event.modifiers()
        blocked_modifiers = Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier | Qt.ShiftModifier
        if int(modifiers & blocked_modifiers) != 0:
            return False

        if not self._numeric_shortcuts_enabled_for_focus():
            return False

        shortcut_index = self._shortcut_index_from_key_event(event)
        if shortcut_index is None:
            return False

        shortcut_labels = self._available_numeric_shortcut_labels()
        if shortcut_index >= len(shortcut_labels):
            self.status('No class mapped for key %d' % (shortcut_index + 1), 2000)
            return True

        label = shortcut_labels[shortcut_index]

        if self.is_classification_mode():
            self.set_classification_label(label)
            self.status('Class shortcut %d: %s' % (shortcut_index + 1, label), 2000)
            return True

        if not self.canvas.editing() or self.label_list.count() == 0:
            return False

        item = self.current_item()
        if item is None and self.canvas.selected_shape is not None:
            item = self.shapes_to_items.get(self.canvas.selected_shape)
        if item is None:
            item = self.label_list.item(self.label_list.count() - 1)
        if item is None:
            return False

        shape = self.items_to_shapes.get(item)
        if shape is None:
            return False

        if shape.label == label:
            self.status('Class shortcut %d: %s' % (shortcut_index + 1, label), 1500)
            return True

        self.label_list.blockSignals(True)
        item.setText(label)
        item.setBackground(generate_color_by_text(label))
        self.label_list.blockSignals(False)

        shape.label = label
        shape.line_color = generate_color_by_text(label)
        self.ensure_label_in_history(label)
        self.set_dirty()
        self._capture_history_state(clear_redo=True)
        self.canvas.update()
        self.update_combo_box()
        self.status('Class shortcut %d: %s' % (shortcut_index + 1, label), 2000)
        return True

    def toggle_compact_mode(self, value=False):
        self.compact_mode_option.setChecked(bool(value))
        self._apply_modern_ui()
        self.status('Compact mode %s' % ('enabled' if self.compact_mode_option.isChecked() else 'disabled'))

    def toggle_modern_icons(self, value=False):
        self.use_modern_icons = bool(value)
        self.modern_icons_option.setChecked(self.use_modern_icons)
        self._apply_modern_ui()
        self.status('Modern icons %s' % ('enabled' if self.use_modern_icons else 'disabled'))

    def toggle_reduced_motion(self, value=False):
        self.reduced_motion = bool(value)
        self.reduced_motion_option.setChecked(self.reduced_motion)
        self._apply_modern_ui()
        self._animate_mode_chip()
        self.status('Reduced motion %s' % ('enabled' if self.reduced_motion else 'disabled'))

    def _refresh_action_icons_in_menu(self, menu):
        for action in menu.actions():
            icon_name = action.property('iconName')
            if icon_name:
                action.setIcon(new_icon(ustr(icon_name)))
            sub_menu = action.menu()
            if sub_menu is not None:
                self._refresh_action_icons_in_menu(sub_menu)

    def refresh_ui_icons(self):
        for menu in self.menuBar().findChildren(QMenu):
            self._refresh_action_icons_in_menu(menu)
        if hasattr(self, 'combo_box') and hasattr(self.combo_box, 'refresh_icon'):
            self.combo_box.refresh_icon()
        if hasattr(self, 'default_label_combo_box') and hasattr(self.default_label_combo_box, 'refresh_icon'):
            self.default_label_combo_box.refresh_icon()
        if hasattr(self, 'training_config_panel') and hasattr(self.training_config_panel, 'refresh_icons'):
            self.training_config_panel.refresh_icons()
        if hasattr(self, 'training_clear_button'):
            self.training_clear_button.setIcon(new_icon('delete'))
        if hasattr(self, 'training_save_button'):
            self.training_save_button.setIcon(new_icon('save'))
        if hasattr(self, 'update_status_chips'):
            self.update_status_chips()

    def show_ui_preferences_preview(self):
        preview = QDialog(self)
        preview.setWindowTitle('UI Preferences Preview')
        preview.setModal(False)

        layout = QVBoxLayout(preview)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(10)

        intro = QLabel('Preview UI options live. Changes apply immediately and are saved when the app closes.')
        intro.setWordWrap(True)
        layout.addWidget(intro)

        compact_cb = QCheckBox('Compact Mode')
        compact_cb.setChecked(self.compact_mode_option.isChecked())
        compact_cb.toggled.connect(self.toggle_compact_mode)

        focus_cb = QCheckBox('Focus Mode')
        focus_cb.setChecked(self.focus_mode_option.isChecked())
        focus_cb.toggled.connect(self.toggle_focus_mode)

        icons_cb = QCheckBox('Modern Icons')
        icons_cb.setChecked(self.modern_icons_option.isChecked())
        icons_cb.toggled.connect(self.toggle_modern_icons)

        motion_cb = QCheckBox('Reduced Motion')
        motion_cb.setChecked(self.reduced_motion_option.isChecked())
        motion_cb.toggled.connect(self.toggle_reduced_motion)

        layout.addWidget(compact_cb)
        layout.addWidget(focus_cb)
        layout.addWidget(icons_cb)
        layout.addWidget(motion_cb)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_btn = QPushButton('Close')
        close_btn.clicked.connect(preview.close)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

        preview.resize(360, 230)
        preview.show()

    def toggle_focus_mode(self, value=False):
        enabled = bool(value)
        self.canvas.set_focus_vignette(enabled)
        if enabled:
            self._focus_mode_restore_state = {
                'menu_bar': self.menuBar().isVisible(),
                'status_bar': self.statusBar().isVisible(),
                'label_dock': self.dock.isVisible(),
                'file_dock': self.file_dock.isVisible(),
                'label_dock_floating': self.dock.isFloating(),
                'file_dock_floating': self.file_dock.isFloating(),
                'toolbars': [(toolbar, toolbar.isVisible()) for toolbar in self.findChildren(QToolBar)],
            }
        self.focus_mode_option.setChecked(enabled)
        if enabled:
            self.menuBar().setVisible(False)
            self.statusBar().setVisible(False)
            if self.dock.isFloating():
                self.dock.setFloating(False)
                self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
            if self.file_dock.isFloating():
                self.file_dock.setFloating(False)
                self.addDockWidget(Qt.RightDockWidgetArea, self.file_dock)
            self.dock.setVisible(True)
            self.file_dock.setVisible(True)
            self.dock.show()
            self.file_dock.show()
            self.label_list.show()
            self.file_list_widget.show()
            self.dock.raise_()
            self.file_dock.raise_()
            self.resizeDocks([self.dock, self.file_dock], [240, 280], Qt.Horizontal)
            for toolbar, _visible in self._focus_mode_restore_state['toolbars']:
                toolbar.setVisible(False)
        else:
            restore_state = self._focus_mode_restore_state or {}
            self.menuBar().setVisible(restore_state.get('menu_bar', True))
            self.statusBar().setVisible(restore_state.get('status_bar', True))
            self.dock.setVisible(restore_state.get('label_dock', True))
            self.file_dock.setVisible(restore_state.get('file_dock', True))
            if restore_state.get('label_dock_floating', False):
                self.dock.setFloating(True)
            if restore_state.get('file_dock_floating', False):
                self.file_dock.setFloating(True)
            for toolbar, visible in restore_state.get('toolbars', []):
                toolbar.setVisible(visible)
            self._focus_mode_restore_state = None
        self.status('Focus mode %s' % ('enabled' if enabled else 'disabled'))

    def exit_focus_mode(self):
        if self.focus_mode_option.isChecked():
            self.toggle_focus_mode(False)

    def update_status_chips(self):
        palette = self._chip_palette()
        mode_meta = self.MODE_STATUS_META.get(self.app_mode, self.MODE_STATUS_META[self.DETECTION_MODE])
        mode_value, mode_key, mode_icon = mode_meta
        mode_text = 'Mode: %s' % mode_value
        if self.label_file_format == LabelFileFormat.PASCAL_VOC:
            format_value = 'PascalVOC'
        elif self.label_file_format == LabelFileFormat.YOLO:
            format_value = 'YOLO'
        else:
            format_value = 'CreateML'
        format_text = 'Format: %s' % format_value
        autosave_text = 'Autosave: %s' % ('ON' if self.auto_saving.isChecked() else 'OFF')
        if hasattr(self, 'mode_status_label'):
            self.mode_status_label.setText(mode_text)
            self.mode_status_label.setIcon(new_icon(mode_icon))
            self._set_chip_style(self.mode_status_label, *palette[mode_key])
        if hasattr(self, 'format_status_label'):
            self.format_status_label.setText(format_text)
            if self.label_file_format == LabelFileFormat.PASCAL_VOC:
                self.format_status_label.setIcon(new_icon('format_voc'))
            elif self.label_file_format == LabelFileFormat.YOLO:
                self.format_status_label.setIcon(new_icon('format_yolo'))
            else:
                self.format_status_label.setIcon(new_icon('format_createml'))
            self._set_chip_style(self.format_status_label, *palette['neutral'])
        if hasattr(self, 'autosave_status_label'):
            self.autosave_status_label.setText(autosave_text)
            self.autosave_status_label.setIcon(new_icon('save' if self.auto_saving.isChecked() else 'cancel'))
            autosave_key = 'autosave_on' if self.auto_saving.isChecked() else 'autosave_off'
            self._set_chip_style(self.autosave_status_label, *palette[autosave_key])
        if hasattr(self, 'image_counter_label'):
            self.image_counter_label.setIcon(new_icon('file'))
            self._set_chip_style(self.image_counter_label, *palette['neutral'])
        self._animate_mode_chip()

    def update_shortcut_hints(self):
        if self.is_training_mode():
            hints = 'Training Mode: configure dataset, review command preview, then start training'
        elif self.is_license_plate_mode():
            draw_mode = 'Square' if self.draw_squares_option.isChecked() else 'Rectangle'
            hints = 'License Plate Mode: Draw W (%s), enter full plate text, save Ctrl+S' % draw_mode
        else:
            draw_mode = 'Square' if self.draw_squares_option.isChecked() else 'Rectangle'
            hints = 'Next: D/Right/PgDown   Prev: A/Left/PgUp   Draw: W (%s)   Class: 1-9   Save: Ctrl+S' % draw_mode
        if hasattr(self, 'shortcut_hints_label'):
            self.shortcut_hints_label.setText(hints)

    def update_image_counter_display(self):
        counter = ''
        if self.img_count > 0 and self.cur_img_idx >= 0:
            counter = self.counter_str()
        if hasattr(self, 'image_counter_label'):
            self.image_counter_label.setText(counter)

    def _serialize_canvas_shapes(self):
        if self.is_classification_mode() or self.image.isNull():
            return []

        state = []
        for shape in self.canvas.shapes:
            line_color = getattr(shape, 'line_color', Shape.line_color)
            fill_color = getattr(shape, 'fill_color', Shape.fill_color)
            state.append({
                'label': shape.label,
                'points': [(point.x(), point.y()) for point in shape.points],
                'difficult': bool(getattr(shape, 'difficult', False)),
                'is_segment': bool(getattr(shape, 'is_segment', False)),
                'max_points': getattr(shape, 'max_points', 4),
                'paint_label': bool(getattr(shape, 'paint_label', False)),
                'line_color': tuple(line_color.getRgb()),
                'fill_color': tuple(fill_color.getRgb()),
                'visible': bool(self.canvas.isVisible(shape)),
            })
        return state

    def _restore_canvas_shapes(self, state):
        self.items_to_shapes.clear()
        self.shapes_to_items.clear()
        self.label_list.clear()

        restored_shapes = []
        for item in state:
            shape = Shape(label=item.get('label'))
            shape.is_segment = bool(item.get('is_segment', False))
            shape.max_points = item.get('max_points', None if shape.is_segment else 4)
            shape.difficult = bool(item.get('difficult', False))
            shape.paint_label = bool(item.get('paint_label', False))

            for x, y in item.get('points', []):
                shape.add_point(QPointF(x, y))
            shape.close()

            line_color = item.get('line_color')
            fill_color = item.get('fill_color')
            if line_color:
                shape.line_color = QColor(*line_color)
            if fill_color:
                shape.fill_color = QColor(*fill_color)

            restored_shapes.append(shape)
            self.add_label(shape)

        self.canvas.load_shapes(restored_shapes)
        for shape, item in zip(restored_shapes, state):
            self.canvas.set_shape_visible(shape, bool(item.get('visible', True)))

        if self.no_shapes():
            for action in self.actions.onShapesPresent:
                action.setEnabled(False)

        self.shape_selection_changed(False)
        self.update_combo_box()
        self.update_classification_ui()

    def _reset_annotation_history(self):
        self.history_service.reset()
        self.update_history_actions()

    def _initialize_annotation_history(self):
        self._reset_annotation_history()
        if self.is_classification_mode() or self.image.isNull():
            return
        state = self._serialize_canvas_shapes()
        self.history_service.initialize(state)
        self.update_history_actions()

    def _capture_history_state(self, clear_redo=True):
        if self.history_service.restoring or self.history_service.suppress_capture:
            return
        if self.is_classification_mode() or self.image.isNull():
            return

        state = self._serialize_canvas_shapes()
        if self.history_service.undo_stack and self.history_service.undo_stack[-1] == state:
            self.update_history_actions()
            return

        self.history_service.capture(state, clear_redo=clear_redo)
        self.update_history_actions()

    def _record_history_checkpoint(self):
        self._capture_history_state(clear_redo=True)

    def update_history_actions(self):
        if not hasattr(self, 'actions'):
            return
        available = (not self.is_classification_mode()) and (not self.image.isNull())
        self.actions.undo.setEnabled(available and self.history_service.can_undo())
        self.actions.redo.setEnabled(available and self.history_service.can_redo())

    def on_canvas_shape_moved(self):
        self.set_dirty()
        checkpoint_enabled = (not self.is_classification_mode()) and (not self.image.isNull())
        self.history_service.request_checkpoint(enabled=checkpoint_enabled)

    def undo_annotation_change(self):
        if self.is_classification_mode() or not self.history_service.can_undo():
            return

        target_state = self.history_service.pop_undo_target()
        if target_state is None:
            return

        self.history_service.start_restore()
        try:
            self._restore_canvas_shapes(target_state)
        finally:
            self.history_service.end_restore()

        if self.history_service.is_at_baseline(target_state):
            self.set_clean()
        else:
            self.set_dirty()
        self.update_history_actions()

    def redo_annotation_change(self):
        if self.is_classification_mode() or not self.history_service.can_redo():
            return

        target_state = self.history_service.pop_redo_target()
        if target_state is None:
            return

        self.history_service.start_restore()
        try:
            self._restore_canvas_shapes(target_state)
        finally:
            self.history_service.end_restore()

        if self.history_service.is_at_baseline(target_state):
            self.set_clean()
        else:
            self.set_dirty()
        self.update_history_actions()

    # Support Functions #
    def is_classification_mode(self):
        return self.app_mode == self.CLASSIFICATION_MODE

    def is_license_plate_mode(self):
        return self.app_mode == self.LICENSE_PLATE_MODE

    def is_segmentation_mode(self):
        return self.app_mode == self.SEGMENTATION_MODE

    def is_training_mode(self):
        return self.app_mode == self.TRAINING_MODE

    def classification_source_dir(self):
        return self.classification_service.resolve_source_dir(
            dir_name=self.dir_name,
            file_path=self.file_path,
            last_open_dir=self.last_open_dir,
        )

    def _update_label_history_widgets(self, preferred_label=None):
        labels = [label for label in self.label_hist if label]
        self.default_label_combo_box.cb.blockSignals(True)
        self.default_label_combo_box.cb.clear()
        self.default_label_combo_box.cb.addItems(labels)
        self.default_label_combo_box.cb.blockSignals(False)

        if labels:
            if preferred_label in labels:
                self.default_label_combo_box.cb.setCurrentIndex(labels.index(preferred_label))
                self.default_label = preferred_label
            elif not getattr(self, 'default_label', None):
                self.default_label = labels[0]

        if self.is_classification_mode():
            self.populate_classification_label_list()

    def ensure_label_in_history(self, label):
        if label and label not in self.label_hist:
            self.label_hist.append(label)
            self.label_hist.sort(key=lambda value: value.lower())
            self._update_label_history_widgets(preferred_label=label)

    def toggle_predefined_classes_lock(self, _value=False):
        self.lock_predefined_classes = bool(self.lock_predefined_classes_checkbox.isChecked())
        if self.lock_predefined_classes:
            self.reload_predefined_classes_from_file()
        self.status(
            self.get_str('lockPredefinedClasses', 'Lock predefined classes') +
            (' enabled' if self.lock_predefined_classes else ' disabled')
        )

    def reload_predefined_classes_from_file(self, _value=False):
        latest_predefined = self._read_predefined_classes_file()
        self.base_label_hist = list(latest_predefined)

        if self.is_predefined_classes_lock_enabled():
            self.label_hist = sorted(self.base_label_hist, key=lambda value: value.lower())
        else:
            merged_labels = {trimmed(label) for label in self.label_hist if trimmed(label)}
            merged_labels.update(self.base_label_hist)
            self.label_hist = sorted(merged_labels, key=lambda value: value.lower())

        self._update_label_history_widgets(preferred_label=getattr(self, 'default_label', None))
        self.label_dialog = LabelDialog(parent=self, list_item=self.label_hist)
        self.status(
            self.get_str('reloadPredefinedClassesDone', 'Reloaded classes from predefined_classes.txt (%d)')
            % len(self.base_label_hist)
        )

    def is_predefined_classes_lock_enabled(self):
        if hasattr(self, 'lock_predefined_classes_checkbox'):
            return bool(self.lock_predefined_classes_checkbox.isChecked())
        return bool(getattr(self, 'lock_predefined_classes', False))

    def _allowed_predefined_labels(self):
        return {trimmed(label) for label in self.base_label_hist if trimmed(label)}

    def _validate_label_against_lock(self, label):
        normalized = trimmed(label)
        if not normalized:
            return False
        if not self.is_predefined_classes_lock_enabled():
            return True
        if normalized in self._allowed_predefined_labels():
            return True
        self.error_message(
            self.get_str('labelLockTitle', 'Predefined classes lock'),
            self.get_str(
                'labelLockBlocked',
                'Class "%s" is not in predefined_classes.txt. Disable lock or add it to the file.'
            ) % normalized,
        )
        return False

    def load_classification_manifest(self, source_dir=None):
        source_dir = source_dir or self.classification_source_dir()
        self.label_hist = list(self.base_label_hist)
        self.classification_labels = {}
        self.classification_manifest_path = None

        if not source_dir or not os.path.isdir(source_dir):
            self._update_label_history_widgets()
            self.update_classification_ui()
            return

        manifest_path = ClassificationSession.default_manifest_path(source_dir)
        try:
            state = self.classification_service.load_manifest_state(
                source_dir=source_dir,
                base_label_hist=self.base_label_hist,
            )
        except ClassificationIOError as e:
            self.error_message(self.get_str('classificationManifestError'), u'<b>%s</b>' % e)
            state = {
                'manifest_path': manifest_path,
                'label_hist': list(self.base_label_hist),
                'classification_labels': {},
            }

        # Keep class history consistent across detection/classification mode switches.
        self.classification_manifest_path = state.get('manifest_path')
        self.label_hist = list(state.get('label_hist') or [])
        self.base_label_hist = list(self.label_hist)
        self._update_label_history_widgets()
        self.classification_labels = dict(state.get('classification_labels') or {})

        self.update_classification_ui()

    def save_classification_manifest(self):
        source_dir = self.classification_source_dir()
        if not source_dir:
            return False

        manifest_path = self.classification_manifest_path or ClassificationSession.default_manifest_path(source_dir)
        try:
            self.classification_service.save_manifest(
                source_dir=source_dir,
                manifest_path=manifest_path,
                label_hist=self.label_hist,
                classification_labels=self.classification_labels,
            )
        except ClassificationIOError as e:
            self.error_message(self.get_str('classificationManifestError'), u'<b>%s</b>' % e)
            return False

        self.classification_manifest_path = manifest_path
        self.set_clean()
        self.refresh_file_list_classification_state()
        return True

    def current_classification_label(self):
        if not self.file_path:
            return None
        return self.classification_labels.get(self.file_path)

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
        self.actions.editMode.setEnabled((not is_classification_mode) and (not is_training_mode) and has_image)
        self.actions.delete.setEnabled((not is_classification_mode) and (not is_training_mode) and has_selected_shape)
        self.actions.copy.setEnabled((not is_classification_mode) and (not is_training_mode) and has_selected_shape)
        self.actions.edit.setEnabled((not is_classification_mode) and (not is_training_mode) and has_selected_shape)
        self.actions.shapeLineColor.setEnabled((not is_classification_mode) and (not is_training_mode) and has_selected_shape)
        self.actions.shapeFillColor.setEnabled((not is_classification_mode) and (not is_training_mode) and has_selected_shape)
        self.actions.verify.setEnabled((not is_classification_mode) and (not is_training_mode) and has_image)
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

    def set_classification_label(self, label):
        if not self.file_path:
            return False

        normalized_label = trimmed(label)
        if not normalized_label:
            return False

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

    def export_classification_dataset(self, _value=False):
        if not self.is_classification_mode() or not self.m_img_list:
            return

        unlabeled = [image_path for image_path in self.m_img_list if not self.classification_labels.get(image_path)]
        if unlabeled:
            self.error_message(self.get_str('classificationExportError'), self.get_str('classificationExportBlocked'))
            return

        default_dir = self.classification_export_dir or self.classification_source_dir() or '.'
        export_dir = ustr(QFileDialog.getExistingDirectory(
            self,
            '%s - %s' % (__appname__, self.get_str('exportClasses')),
            default_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks))

        if not export_dir:
            return

        dataset_name, ok = QInputDialog.getText(
            self,
            self.get_str('exportClasses'),
            self.get_str('datasetFolderName'),
            text='dataset')
        dataset_name = trimmed(dataset_name)
        if not ok or not dataset_name:
            return

        dataset_root = os.path.join(export_dir, dataset_name)

        source_dir = self.classification_source_dir()
        session = self.classification_service.build_export_session(
            source_dir=source_dir,
            label_hist=self.label_hist,
            classification_labels=self.classification_labels,
        )
        try:
            session.export_dataset(dataset_root, move_images=True)
        except ClassificationIOError as e:
            self.error_message(self.get_str('classificationExportError'), u'<b>%s</b>' % e)
            return

        zip_question = QMessageBox.question(
            self,
            self.get_str('exportClasses'),
            self.get_str('exportZipQuestion'),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No)
        if zip_question == QMessageBox.Yes:
            try:
                shutil.make_archive(dataset_root, 'zip', os.path.dirname(dataset_root), os.path.basename(dataset_root))
            except Exception as e:
                self.error_message(self.get_str('classificationExportError'), u'<b>%s</b>' % e)
                return

        self.classification_export_dir = export_dir
        self.settings[SETTING_CLASSIFICATION_EXPORT_DIR] = export_dir
        self.status(self.get_str('classificationExportDone'))
        self.classification_labels = {}
        self.set_clean()
        if source_dir:
            self.import_dir_images(source_dir)

    def export_license_plate_dataset(self, _value=False):
        if not self.is_license_plate_mode() or not self.m_img_list:
            return

        source_dir = self.classification_source_dir()
        if not source_dir:
            self.error_message(
                self.get_str('licensePlateExportError', 'License plate export error'),
                self.get_str('licensePlateSourceDirError', 'Could not resolve source image directory.'))
            return

        default_dir = self.license_plate_export_dir or source_dir or '.'
        export_dir = ustr(QFileDialog.getExistingDirectory(
            self,
            '%s - %s' % (__appname__, self.get_str('exportLicensePlateDataset', 'Export License Plate Dataset')),
            default_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks))
        if not export_dir:
            return

        dataset_name, ok = QInputDialog.getText(
            self,
            self.get_str('exportLicensePlateDataset', 'Export License Plate Dataset'),
            self.get_str('datasetFolderName'),
            text='license_plate_dataset')
        dataset_name = trimmed(dataset_name)
        if not ok or not dataset_name:
            return

        transfer_box = QMessageBox(self)
        transfer_box.setWindowTitle(self.get_str('exportLicensePlateDataset', 'Export License Plate Dataset'))
        transfer_box.setText(self.get_str(
            'licensePlateTransferMode',
            'Choose export mode: Copy keeps source files, Move relocates source files.'))
        copy_button = transfer_box.addButton(self.get_str('copyMode', 'Copy'), QMessageBox.AcceptRole)
        move_button = transfer_box.addButton(self.get_str('moveMode', 'Move'), QMessageBox.DestructiveRole)
        transfer_box.addButton(QMessageBox.Cancel)
        transfer_box.exec_()
        clicked = transfer_box.clickedButton()
        if clicked == copy_button:
            move_images = False
        elif clicked == move_button:
            move_images = True
        else:
            return

        dataset_root = os.path.join(export_dir, dataset_name)
        session = LicensePlateDatasetSession(source_dir=source_dir)
        try:
            result = session.export_dataset(
                output_dir=dataset_root,
                image_paths=self.m_img_list,
                move_images=move_images,
                skip_unlabeled=True,
            )
        except LicensePlateIOError as e:
            self.error_message(self.get_str('licensePlateExportError', 'License plate export error'), u'<b>%s</b>' % e)
            return

        summary = self.get_str('licensePlateExportSummary',
                               'Exported pairs: %d\nSkipped unlabeled: %d\nMode: %s\nDataset: %s') % (
            result.get('exported_count', 0),
            result.get('skipped_unlabeled', 0),
            self.get_str('moveMode', 'Move') if move_images else self.get_str('copyMode', 'Copy'),
            result.get('output_dir', dataset_root),
        )
        QMessageBox.information(self, self.get_str('exportLicensePlateDataset', 'Export License Plate Dataset'), summary)

        zip_question = QMessageBox.question(
            self,
            self.get_str('exportLicensePlateDataset', 'Export License Plate Dataset'),
            self.get_str('exportZipQuestion', 'Create a .zip file for the exported dataset?'),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No)
        if zip_question == QMessageBox.Yes:
            try:
                shutil.make_archive(dataset_root, 'zip', os.path.dirname(dataset_root), os.path.basename(dataset_root))
            except Exception as e:
                self.error_message(self.get_str('licensePlateExportError', 'License plate export error'), u'<b>%s</b>' % e)
                return

        self.license_plate_export_dir = export_dir
        self.settings[SETTING_LICENSE_PLATE_EXPORT_DIR] = export_dir
        self.status(self.get_str('licensePlateExportDone', 'License plate dataset export completed.'))

        if move_images:
            self.set_clean()
            self.import_dir_images(source_dir)

    def _ask_split_percentages(self):
        train_percent, ok = QInputDialog.getInt(
            self,
            self.get_str('exportYOLODataset', 'Export YOLO Dataset'),
            self.get_str('yoloTrainPercent', 'Train split percentage (0-100):'),
            value=80,
            min=0,
            max=100)
        if not ok:
            return None

        test_percent, ok = QInputDialog.getInt(
            self,
            self.get_str('exportYOLODataset', 'Export YOLO Dataset'),
            self.get_str('yoloTestPercent', 'Test split percentage (0-100):'),
            value=10,
            min=0,
            max=100)
        if not ok:
            return None

        valid_percent, ok = QInputDialog.getInt(
            self,
            self.get_str('exportYOLODataset', 'Export YOLO Dataset'),
            self.get_str('yoloValidPercent', 'Valid split percentage (0-100):'),
            value=10,
            min=0,
            max=100)
        if not ok:
            return None

        if train_percent + test_percent + valid_percent != 100:
            self.error_message(
                self.get_str('yoloExportError', 'YOLO dataset export error'),
                self.get_str('yoloSplitInvalid', 'Split ratios must sum to 100.'))
            return None

        return train_percent, test_percent, valid_percent

    def _ask_yolo_random_seed(self):
        seed, ok = QInputDialog.getInt(
            self,
            self.get_str('exportYOLODataset', 'Export YOLO Dataset'),
            self.get_str('yoloRandomSeed', 'Random seed for split (same seed = same split):'),
            value=42,
            min=0,
            max=2 ** 31 - 1)
        if not ok:
            return None
        return seed

    def _ask_show_split_preview(self):
        decision = QMessageBox.question(
            self,
            self.get_str('exportYOLODataset', 'Export YOLO Dataset'),
            self.get_str('yoloPreviewAsk', 'Show split preview before export?'),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes)
        return decision == QMessageBox.Yes

    def _ask_stratified_split(self):
        decision = QMessageBox.question(
            self,
            self.get_str('exportYOLODataset', 'Export YOLO Dataset'),
            self.get_str('yoloStratifiedSplit', 'Use stratified split by dominant class?'),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No)
        return decision == QMessageBox.Yes

    def _show_yolo_split_preview(self, preview, train_percent, test_percent, valid_percent, seed):
        counts = preview.get('counts', {})
        quality = preview.get('quality', {})
        duplicate_count = len(quality.get('duplicate_groups', []))
        message = (
            '%s\n\n'
            'Seed: %d\n'
            'Ratios: Train %d%%, Test %d%%, Valid %d%%\n\n'
            'Labeled images: %d\n'
            'Skipped unlabeled: %d\n\n'
            'Empty label files: %d\n'
            'Duplicate image groups: %d\n\n'
            'Planned split counts:\n'
            'Train: %d\n'
            'Test: %d\n'
            'Valid: %d\n\n'
            '%s'
        ) % (
            self.get_str('yoloPreviewTitle', 'Split preview'),
            seed,
            train_percent,
            test_percent,
            valid_percent,
            preview.get('total_labeled', 0),
            preview.get('skipped_unlabeled', 0),
            len(quality.get('empty_label_images', [])),
            duplicate_count,
            counts.get('train', 0),
            counts.get('test', 0),
            counts.get('valid', 0),
            self.get_str('yoloPreviewContinue', 'Continue export?')
        )

        choice = QMessageBox.question(
            self,
            self.get_str('exportYOLODataset', 'Export YOLO Dataset'),
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes)
        return choice == QMessageBox.Yes

    def _run_yolo_export_config_dialog(self, default_dir):
        strings = {
            'browse': self.get_str('yoloConfigBrowse', 'Browse'),
            'exportDir': self.get_str('yoloConfigExportDir', 'Export folder'),
            'datasetName': self.get_str('yoloConfigDatasetName', 'Dataset folder name'),
            'trainPercent': self.get_str('yoloConfigTrainPercent', 'Train (%)'),
            'testPercent': self.get_str('yoloConfigTestPercent', 'Test (%)'),
            'validPercent': self.get_str('yoloConfigValidPercent', 'Valid (%)'),
            'splitSum': self.get_str('yoloConfigSplitSum', 'Split sum'),
            'stratified': self.get_str('yoloConfigStratified', 'Use stratified split by dominant class'),
            'shuffle': self.get_str('yoloConfigShuffle', 'Shuffle before split'),
            'seed': self.get_str('yoloConfigSeed', 'Random seed'),
            'preview': self.get_str('yoloConfigPreview', 'Show split preview before export'),
            'zip': self.get_str('yoloConfigZip', 'Create zip after export'),
            'chooseExportDirTitle': self.get_str('yoloConfigChooseExportDir', 'Choose export folder'),
            'splitSumOk': self.get_str('yoloConfigSplitSumOk', '100 (OK)'),
            'splitSumInvalid': self.get_str('yoloConfigSplitSumInvalid', 'Must be 100 (current: %d)'),
            'missingExportDir': self.get_str('yoloConfigMissingExportDir', 'Please choose an export folder.'),
            'invalidExportDir': self.get_str('yoloConfigInvalidExportDir', 'Export folder does not exist.'),
            'missingDatasetName': self.get_str('yoloConfigMissingDatasetName', 'Please enter dataset folder name.'),
            'invalidSplit': self.get_str('yoloSplitInvalid', 'Split ratios must sum to 100.'),
        }
        defaults = {
            'export_dir': default_dir,
            'dataset_name': 'yolo_dataset',
            'train_percent': 80,
            'test_percent': 10,
            'valid_percent': 10,
            'stratified': False,
            'shuffle': True,
            'seed': 42,
            'show_preview': True,
            'create_zip': False,
        }
        dialog = YOLOExportConfigDialog(
            self,
            title=self.get_str('exportYOLODataset', 'Export YOLO Dataset'),
            defaults=defaults,
            strings=strings,
        )
        return dialog.get_config()

    def export_yolo_dataset(self, _value=False):
        if self.is_classification_mode() or not self.m_img_list:
            return

        source_dir = self.dir_name or (os.path.dirname(self.file_path) if self.file_path else None)
        if not source_dir:
            self.error_message(self.get_str('yoloExportError', 'YOLO dataset export error'), 'Could not resolve source image directory.')
            return

        default_dir = self.yolo_export_dir or source_dir or '.'
        config = self._run_yolo_export_config_dialog(default_dir)
        if not config:
            return

        export_dir = config.get('export_dir')
        dataset_name = config.get('dataset_name')
        train_percent = config.get('train_percent', 80)
        test_percent = config.get('test_percent', 10)
        valid_percent = config.get('valid_percent', 10)
        stratified = bool(config.get('stratified', False))
        shuffle = bool(config.get('shuffle', True))
        seed = int(config.get('seed', 42))
        show_preview_requested = bool(config.get('show_preview', True))
        create_zip = bool(config.get('create_zip', False))

        dataset_root = os.path.join(export_dir, dataset_name)
        session = YOLODatasetSession(source_dir=source_dir, seed=seed)

        try:
            preview = session.preview_split(
                image_paths=self.m_img_list,
                train_percent=train_percent,
                test_percent=test_percent,
                valid_percent=valid_percent,
                skip_unlabeled=True,
                stratified=stratified,
                shuffle=shuffle)
        except YOLODatasetExportError as e:
            self.error_message(self.get_str('yoloExportError', 'YOLO dataset export error'), u'<b>%s</b>' % e)
            return

        quality = preview.get('quality', {})
        invalid_count = len(quality.get('invalid_class_images', []))
        if invalid_count:
            self.error_message(
                self.get_str('yoloExportError', 'YOLO dataset export error'),
                '%s\n\nInvalid files: %d' % (
                    self.get_str('yoloClassConsistencyError', 'Class consistency check failed. Some txt files use class index outside classes.txt.'),
                    invalid_count,
                )
            )
            return

        skipped = preview.get('skipped_unlabeled', 0)
        empty = len(quality.get('empty_label_images', []))
        if skipped + empty > 0:
            warn_msg = '%s\n\nSkipped unlabeled: %d\nEmpty labels: %d\n\nContinue?' % (
                self.get_str('yoloGuardManyMissing', 'Warning: many images are unlabeled or empty.'),
                skipped,
                empty,
            )
            warn_decision = QMessageBox.question(
                self,
                self.get_str('exportYOLODataset', 'Export YOLO Dataset'),
                warn_msg,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes)
            if warn_decision != QMessageBox.Yes:
                return

        if show_preview_requested:
            if not self._show_yolo_split_preview(preview, train_percent, test_percent, valid_percent, seed):
                return

        try:
            result = session.export_dataset(
                output_dir=dataset_root,
                image_paths=self.m_img_list,
                train_percent=train_percent,
                test_percent=test_percent,
                valid_percent=valid_percent,
                copy_images=True,
                skip_unlabeled=True,
                write_yaml=True,
                stratified=stratified,
                shuffle=shuffle,
                write_stats=True)
        except YOLODatasetExportError as e:
            self.error_message(self.get_str('yoloExportError', 'YOLO dataset export error'), u'<b>%s</b>' % e)
            return

        self.yolo_export_dir = export_dir
        self.settings[SETTING_YOLO_EXPORT_DIR] = export_dir
        self.last_exported_dataset_yaml = result.get('yaml_path', '')
        self.settings[SETTING_YOLO_LAST_DATASET_YAML] = self.last_exported_dataset_yaml

        exported = result.get('exported', {})
        summary = (
            '%s\n\n'
            'Train: %d\n'
            'Test: %d\n'
            'Valid: %d\n'
            'Total labeled exported: %d\n'
            '%s\n'
            'YAML: %s\n'
            '%s: %s\n'
            'Stratified split: %s\n'
            'Shuffle: %s\n'
            'Output: %s'
        ) % (
            self.get_str('yoloExportDone', 'YOLO dataset export completed.'),
            exported.get('train', 0),
            exported.get('test', 0),
            exported.get('valid', 0),
            result.get('total_labeled', 0),
            self.get_str('yoloSkipSummary', 'Skipped unlabeled images: %d') % result.get('skipped_unlabeled', 0),
            result.get('yaml_path', ''),
            self.get_str('yoloStatsReport', 'Stats report'),
            result.get('stats_path', ''),
            'Yes' if result.get('stratified') else 'No',
            'Yes' if result.get('shuffle', True) else 'No',
            result.get('output_dir', ''),
        )
        QMessageBox.information(self, self.get_str('exportYOLODataset', 'Export YOLO Dataset'), summary)

        if create_zip:
            try:
                shutil.make_archive(dataset_root, 'zip', os.path.dirname(dataset_root), os.path.basename(dataset_root))
            except Exception as e:
                self.error_message(self.get_str('yoloExportError', 'YOLO dataset export error'), u'<b>%s</b>' % e)
                return

            delete_question = self.get_str(
                'yoloDeleteSourceAfterZipQuestion',
                'Delete source images and txt labels from the current directory now?')
            delete_warning = self.get_str(
                'yoloDeleteSourceAfterZipWarning',
                'This will permanently delete source images and txt labels under:\n%s') % source_dir
            delete_choice = QMessageBox.question(
                self,
                self.get_str('exportYOLODataset', 'Export YOLO Dataset'),
                '%s\n\n%s' % (delete_question, delete_warning),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No)
            if delete_choice == QMessageBox.Yes:
                typed_text, typed_ok = QInputDialog.getText(
                    self,
                    self.get_str('exportYOLODataset', 'Export YOLO Dataset'),
                    self.get_str('yoloDeleteSourceTypeConfirm', 'Type YES to confirm deletion, or NO to cancel:')
                )
                typed_text = trimmed(typed_text).upper()
                if not typed_ok or typed_text == 'NO':
                    self.status(self.get_str('yoloDeleteSourceTypeCancelled', 'Delete cancelled.'))
                elif typed_text == 'YES':
                    try:
                        self._delete_source_images_and_txt(source_dir)
                    except Exception as e:
                        self.error_message(self.get_str('yoloExportError', 'YOLO dataset export error'), u'<b>%s</b>' % e)
                        return
                    self.status(self.get_str('yoloDeleteSourceAfterZipDone', 'Source images and txt labels deleted.'))
                else:
                    self.status(self.get_str('yoloDeleteSourceTypeInvalid', 'Invalid input: type YES to delete or NO to cancel.'))

        self.status(self.get_str('yoloExportDone', 'YOLO dataset export completed.'))

    def _delete_source_images_and_txt(self, source_dir):
        image_paths = set(self.scan_all_images(source_dir))
        txt_paths = set()
        for image_path in image_paths:
            txt_paths.add(os.path.splitext(image_path)[0] + TXT_EXT)

        # Also remove classes.txt in the source root when user confirms cleanup.
        txt_paths.add(os.path.join(source_dir, 'classes.txt'))

        for file_path in image_paths:
            if os.path.exists(file_path):
                os.remove(file_path)

        for file_path in txt_paths:
            if os.path.exists(file_path):
                os.remove(file_path)

        if source_dir == self.dir_name:
            self.set_clean()
            self.import_dir_images(source_dir)

    def save_training_logs(self):
        if not self.training_log_text.toPlainText().strip():
            self.status('No training logs to save.', 2000)
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            'Save training logs',
            os.path.join(self.current_path(), 'training.log'),
            'Log Files (*.log);;Text Files (*.txt);;All Files (*)')
        if isinstance(output_path, tuple):
            output_path = output_path[0]
        if not output_path:
            return

        try:
            with open(output_path, 'w', encoding='utf-8') as handle:
                handle.write(self.training_log_text.toPlainText())
        except Exception as exc:
            self.error_message('Save training logs', 'Could not save logs:\n%s' % exc)
            return
        self.status('Training logs saved: %s' % output_path)

    def _training_defaults(self):
        return self.training_state_service.defaults(
            settings=self.settings,
            current_path=self.current_path(),
            last_exported_dataset_yaml=self.last_exported_dataset_yaml,
        )

    def _persist_training_defaults(self, config):
        self.training_state_service.persist_defaults(self.settings, config)

    def _append_training_log(self, message):
        self.training_log_text.appendPlainText(message)
        parsed = parse_yolov8_progress_line(message)
        if parsed:
            self._update_training_progress_state(parsed)

    def _update_training_progress_state(self, parsed):
        ui_state = self.training_state_service.apply_progress_update(self.training_progress_state, parsed)
        if ui_state.get('epoch_text'):
            self.training_epoch_label.setText(ui_state['epoch_text'])
        if ui_state.get('progress_value') is not None:
            self.training_progress_bar.setValue(ui_state['progress_value'])
        if ui_state.get('eta_text'):
            self.training_eta_label.setText(ui_state['eta_text'])
        if ui_state.get('metrics_text'):
            self.training_metrics_label.setText(ui_state['metrics_text'])

    def _format_elapsed(self, seconds):
        return self.training_state_service.format_elapsed(seconds)

    def _update_training_summary(self, config=None, artifacts=None):
        config = config or self._active_training_config or {}
        self.training_summary_label.setText(
            self.training_state_service.summary_text(config=config, artifacts=artifacts)
        )

    def open_train_dialog(self, _value=False):
        self.toggle_training_mode(True)

    def _refresh_training_panel_defaults(self):
        defaults = self._training_defaults()
        if defaults.get('source_mode') == 'last_export' and not defaults.get('last_export_yaml'):
            defaults['source_mode'] = 'existing_yaml'
        self.training_config_panel.set_defaults(defaults)

    def start_training_from_panel(self, config):
        if config.get('source_mode') == 'last_export' and not self.last_exported_dataset_yaml:
            self.error_message('Train YOLOv8', self.get_str('trainingNoDatasetYaml', 'No dataset.yaml available from last export. Please choose an existing dataset.yaml.'))
            return
        self._persist_training_defaults(config)
        self._start_training_run(config)

    def exit_training_mode(self):
        self.toggle_detection_mode(True)

    def _set_training_running(self, running):
        self.training_running = bool(running)
        self.update_classification_ui()

    def _start_training_run(self, config):
        self.training_log_dock.show()
        self.training_log_dock.raise_()
        command = config.get('command', [])
        self._active_training_config = dict(config)
        self.training_progress_state = {
            'started_at': time.time(),
        }
        self.training_status_label.setText('Status: Running')
        self.training_epoch_label.setText('Epoch: -')
        self.training_eta_label.setText('ETA: estimating...')
        self.training_metrics_label.setText('Metrics: -')
        self.training_progress_bar.setValue(0)
        self._update_training_summary(config=config)
        self._append_training_log('$ %s' % format_command_for_display(command))
        self.training_worker = TrainingWorker(command, parent=self)
        self.training_worker.run_started.connect(self._on_training_started)
        self.training_worker.log_line.connect(self._append_training_log)
        self.training_worker.run_failed.connect(self._on_training_failed)
        self.training_worker.run_stopped.connect(self._on_training_stopped)
        self.training_worker.run_finished.connect(self._on_training_finished)
        self._set_training_running(True)
        self.training_worker.start()

    def _clear_training_worker(self):
        if self.training_worker is not None:
            self.training_worker.deleteLater()
        self.training_worker = None
        self._set_training_running(False)

    def _on_training_started(self):
        self.training_status_label.setText('Status: Running')
        self.training_eta_label.setText('ETA: estimating...')
        self.training_progress_bar.setValue(0)
        self.status(self.get_str('trainingStart', 'Training started.'))

    def _on_training_failed(self, message):
        self._append_training_log('[error] %s' % message)
        elapsed = self._format_elapsed(time.time() - self.training_progress_state.get('started_at', time.time()))
        self.training_status_label.setText('Status: Failed (%s)' % elapsed)
        self.training_eta_label.setText('ETA: unavailable')
        self.training_progress_bar.setFormat('Training failed at %p%%')
        self.status(self.get_str('trainingFailed', 'Training failed.'))
        self._clear_training_worker()
        self.error_message('Train YOLOv8', message)

    def _on_training_stopped(self):
        self._append_training_log('[stopped] Training interrupted by user.')
        elapsed = self._format_elapsed(time.time() - self.training_progress_state.get('started_at', time.time()))
        self.training_status_label.setText('Status: Stopped (%s)' % elapsed)
        self.training_eta_label.setText('ETA: stopped')
        self.training_progress_bar.setFormat('Training stopped at %p%%')
        self.status(self.get_str('trainingStopped', 'Training stopped.'))
        self._clear_training_worker()

    def _on_training_finished(self, info):
        self.status(self.get_str('trainingComplete', 'Training completed.'))
        exit_code = info.get('exit_code', 0)
        config = self._active_training_config or {}
        artifacts = infer_run_artifacts(config.get('output_dir', ''), config.get('run_name', ''))
        elapsed = self._format_elapsed(time.time() - self.training_progress_state.get('started_at', time.time()))
        self.training_status_label.setText('Status: Completed (%s)' % elapsed)
        self.training_eta_label.setText('ETA: 0s')
        self.training_progress_bar.setFormat('Training progress: %p%')
        self.training_progress_bar.setValue(100)
        self._update_training_summary(config=config, artifacts=artifacts)
        self._append_training_log('[done] Exit code: %s' % exit_code)
        self._append_training_log('[done] Run directory: %s' % artifacts.get('run_dir', ''))
        if artifacts.get('best_pt'):
            self._append_training_log('[done] Best checkpoint: %s' % artifacts.get('best_pt'))

        epoch_text = self.training_state_service.epoch_fraction(self.training_progress_state)
        metrics_text = self.training_state_service.metrics_compact_text(self.training_progress_state)

        box = QMessageBox(self)
        box.setWindowTitle('Train YOLOv8')
        details = [
            self.get_str('trainingComplete', 'Training completed.'),
            '',
            'Elapsed: %s' % elapsed,
            'Last epoch: %s' % epoch_text,
            'Last metrics: %s' % metrics_text,
            '',
            'Run directory: %s' % artifacts.get('run_dir', ''),
            'best.pt: %s' % (artifacts.get('best_pt', '') or 'not found'),
        ]
        box.setText('\n'.join(details))
        open_button = box.addButton('Open Folder', QMessageBox.ActionRole)
        box.addButton(QMessageBox.Ok)
        box.exec_()
        if box.clickedButton() == open_button and artifacts.get('run_dir'):
            QDesktopServices.openUrl(QUrl.fromLocalFile(artifacts['run_dir']))

        self._clear_training_worker()

    def stop_training_process(self, _value=False):
        if not self.training_running or self.training_worker is None:
            return
        stop_confirm = QMessageBox.question(
            self,
            'Train YOLOv8',
            'Stop the running training process?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No)
        if stop_confirm != QMessageBox.Yes:
            return
        self.training_worker.stop()

    def set_format(self, save_format):
        if save_format == FORMAT_PASCALVOC:
            self.actions.save_format.setText(FORMAT_PASCALVOC)
            self.actions.save_format.setIcon(new_icon("format_voc"))
            self.label_file_format = LabelFileFormat.PASCAL_VOC
            LabelFile.suffix = XML_EXT

        elif save_format == FORMAT_YOLO:
            self.actions.save_format.setText(FORMAT_YOLO)
            self.actions.save_format.setIcon(new_icon("format_yolo"))
            self.label_file_format = LabelFileFormat.YOLO
            LabelFile.suffix = TXT_EXT

        elif save_format == FORMAT_CREATEML:
            self.actions.save_format.setText(FORMAT_CREATEML)
            self.actions.save_format.setIcon(new_icon("format_createml"))
            self.label_file_format = LabelFileFormat.CREATE_ML
            LabelFile.suffix = JSON_EXT

        self.update_status_chips()

    def change_format(self):
        if self.label_file_format == LabelFileFormat.PASCAL_VOC:
            self.set_format(FORMAT_YOLO)
        elif self.label_file_format == LabelFileFormat.YOLO:
            self.set_format(FORMAT_CREATEML)
        elif self.label_file_format == LabelFileFormat.CREATE_ML:
            self.set_format(FORMAT_PASCALVOC)
        else:
            raise ValueError('Unknown label file format.')
        self.set_dirty()

    def no_shapes(self):
        return not self.items_to_shapes

    def toggle_advanced_mode(self, value=True):
        if self.is_classification_mode():
            return
        self._beginner = not value
        self.canvas.set_editing(True)
        self.populate_mode_actions()
        self.edit_button.setVisible(not value)
        if value:
            self.actions.createMode.setEnabled(True)
            self.actions.editMode.setEnabled(False)
            self.dock.setFeatures(self.dock.features() | self.dock_features)
        else:
            self.dock.setFeatures(self.dock.features() ^ self.dock_features)

    def populate_mode_actions(self):
        self.mode_controller.populate_mode_actions()

    def toggle_detection_mode(self, value=True):
        self.mode_controller.toggle_detection_mode(value=value)

    def toggle_classification_mode(self, value=True):
        self.mode_controller.toggle_classification_mode(value=value)

    def toggle_license_plate_mode(self, value=True):
        self.mode_controller.toggle_license_plate_mode(value=value)

    def toggle_segmentation_mode(self, value=True):
        self.mode_controller.toggle_segmentation_mode(value=value)

    def toggle_training_mode(self, value=True):
        self.mode_controller.toggle_training_mode(value=value)

    def set_beginner(self):
        self.tools.clear()
        add_actions(self.tools, self.actions.beginner)

    def set_advanced(self):
        self.tools.clear()
        add_actions(self.tools, self.actions.advanced)

    def set_dirty(self):
        self.dirty = True
        self.actions.save.setEnabled(True)
        self.update_classification_ui()

    def set_clean(self):
        self.dirty = False
        self.actions.save.setEnabled(False)
        self.actions.create.setEnabled(True)
        self.update_classification_ui()

    def toggle_actions(self, value=True):
        """Enable/Disable widgets which depend on an opened image."""
        for z in self.actions.zoomActions:
            z.setEnabled(value)
        for z in self.actions.lightActions:
            z.setEnabled(value)
        for action in self.actions.onLoadActive:
            action.setEnabled(value)
        self.update_classification_ui()

    def queue_event(self, function):
        QTimer.singleShot(0, function)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def reset_state(self):
        self._reset_annotation_history()
        self.items_to_shapes.clear()
        self.shapes_to_items.clear()
        self.label_list.clear()
        self.file_path = None
        self.image_data = None
        self.label_file = None
        self.image = QImage()  # Ensure image is always reset to null
        self.canvas.reset_state()
        self.label_coordinates.clear()
        self.update_image_counter_display()
        self.combo_box.cb.clear()
        self.update_classification_ui()

    def current_item(self):
        items = self.label_list.selectedItems()
        if items:
            return items[0]
        return None

    def add_recent_file(self, file_path):
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        elif len(self.recent_files) >= self.max_recent:
            self.recent_files.pop()
        self.recent_files.insert(0, file_path)

    def beginner(self):
        return self._beginner

    def advanced(self):
        return not self.beginner()

    def show_tutorial_dialog(self, browser='default', link=None):
        if link is None:
            link = self.screencast

        if browser.lower() == 'default':
            wb.open(link, new=2)
        elif browser.lower() == 'chrome' and self.os_name == 'Windows':
            if shutil.which(browser.lower()):  # 'chrome' not in wb._browsers in windows
                wb.register('chrome', None, wb.BackgroundBrowser('chrome'))
            else:
                chrome_path="D:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
                if os.path.isfile(chrome_path):
                    wb.register('chrome', None, wb.BackgroundBrowser(chrome_path))
            try:
                wb.get('chrome').open(link, new=2)
            except wb.Error:
                wb.open(link, new=2)
        elif browser.lower() in wb._browsers:
            wb.get(browser.lower()).open(link, new=2)

    def show_default_tutorial_dialog(self):
        self.show_tutorial_dialog(browser='default')

    def show_info_dialog(self):
        from libs.__init__ import __version__
        msg = u'Name:{0} \nApp Version:{1} \n{2} '.format(__appname__, __version__, sys.version_info)
        QMessageBox.information(self, u'Information', msg)

    def show_shortcuts_dialog(self):
        shortcuts_text = (
            'Navigation\n'
            '  Next Image: D / Right / PgDown\n'
            '  Previous Image: A / Left / PgUp\n'
            '\n'
            'Annotation\n'
            '  Draw Box: W\n'
            '  Toggle Draw Square: Ctrl+Shift+R\n'
            '  Quick Class Select: 1-9\n'
            '  Detection Mode: Ctrl+Shift+D\n'
            '  Classification Mode: Ctrl+Shift+C\n'
            '  License Plate Mode: Ctrl+Shift+N\n'
            '  Segmentation Mode: Ctrl+Shift+G\n'
            '  Training Mode: Ctrl+Shift+K\n'
            '  Finalize Polygon: Enter or Double Click\n'
            '  Verify Image: Space\n'
            '\n'
            'File\n'
            '  Open File: Ctrl+O\n'
            '  Open Folder: Ctrl+U\n'
            '  Save: Ctrl+S\n'
            '  Delete Current Image: Ctrl+Shift+X\n'
            '\n'
            'View\n'
            '  Compact Mode: Ctrl+Shift+M\n'
            '  Focus Mode: F11\n'
            '  Shortcuts Help: ?\n'
        )
        QMessageBox.information(self, 'Keyboard Shortcuts', shortcuts_text)

    def show_mode_shortcuts_dialog(self):
        shortcuts_text = (
            'Mode Switching\n'
            '  Detection Mode: Ctrl+Shift+D\n'
            '  Classification Mode: Ctrl+Shift+C\n'
            '  License Plate Mode: Ctrl+Shift+N\n'
            '  Segmentation Mode: Ctrl+Shift+G\n'
            '  Training Mode: Ctrl+Shift+K\n'
        )
        QMessageBox.information(self, self.get_str('modeShortcuts', 'Mode Shortcuts'), shortcuts_text)

    def create_shape(self):
        assert self.beginner()
        self.canvas.set_editing(False)
        self.actions.create.setEnabled(False)

    def toggle_drawing_sensitive(self, drawing=True):
        """In the middle of drawing, toggling between modes should be disabled."""
        self.actions.editMode.setEnabled(not drawing)
        if not drawing and self.beginner():
            # Cancel creation.
            print('Cancel creation.')
            self.canvas.set_editing(True)
            self.canvas.restore_cursor()
            self.actions.create.setEnabled(True)

    def toggle_draw_mode(self, edit=True):
        self.canvas.set_editing(edit)
        self.actions.createMode.setEnabled(edit)
        self.actions.editMode.setEnabled(not edit)

    def set_create_mode(self):
        assert self.advanced()
        self.toggle_draw_mode(False)

    def set_edit_mode(self):
        assert self.advanced()
        self.toggle_draw_mode(True)
        self.label_selection_changed()

    def update_file_menu(self):
        curr_file_path = self.file_path

        def exists(filename):
            return os.path.exists(filename)
        menu = self.menus.recentFiles
        menu.clear()
        files = [f for f in self.recent_files if f !=
                 curr_file_path and exists(f)]
        for i, f in enumerate(files):
            icon = new_icon('labels')
            action = QAction(
                icon, '&%d %s' % (i + 1, QFileInfo(f).fileName()), self)
            action.triggered.connect(partial(self.load_recent, f))
            menu.addAction(action)

    def pop_label_list_menu(self, point):
        self.menus.labelList.exec_(self.label_list.mapToGlobal(point))

    def edit_label(self):
        if self.is_classification_mode():
            self.assign_classification_label()
            return
        if self.is_license_plate_mode():
            item = self.current_item()
            if not item:
                return
            text = self._prompt_license_plate_text(item.text())
            if text is not None:
                item.setText(text)
                item.setBackground(generate_color_by_text(text))
                self.set_dirty()
                self._capture_history_state(clear_redo=True)
                self.update_combo_box()
            return
        if not self.canvas.editing():
            return
        item = self.current_item()
        if not item:
            return
        text = self.label_dialog.pop_up(item.text())
        if text is not None:
            text = trimmed(text)
            if not self._validate_label_against_lock(text):
                return
            item.setText(text)
            item.setBackground(generate_color_by_text(text))
            self.set_dirty()
            self._capture_history_state(clear_redo=True)
            self.update_combo_box()

    def handle_label_list_click(self, item):
        if self.is_classification_mode() and item is not None:
            self.set_classification_label(item.text())

    # Tzutalin 20160906 : Add file list and dock to move faster
    def file_item_double_clicked(self, item=None):
        self.cur_img_idx = self.m_img_list.index(ustr(item.text()))
        filename = self.m_img_list[self.cur_img_idx]
        if filename:
            self.load_file(filename)

    # Add chris
    def button_state(self, item=None):
        """ Function to handle difficult examples
        Update on each object """
        if self.is_classification_mode():
            return
        if not self.canvas.editing():
            return

        item = self.current_item()
        if not item:  # If not selected Item, take the first one
            item = self.label_list.item(self.label_list.count() - 1)
        if item is None:
            return

        difficult = self.diffc_button.isChecked()
        shape = self.items_to_shapes.get(item)
        if shape is None:
            return

        # Checked and Update
        if difficult != shape.difficult:
            shape.difficult = difficult
            self.set_dirty()
            self._capture_history_state(clear_redo=True)
        else:  # User probably changed item visibility
            self.canvas.set_shape_visible(shape, item.checkState() == Qt.Checked)
            self._capture_history_state(clear_redo=True)

    # React to canvas signals.
    def shape_selection_changed(self, selected=False):
        if self.is_classification_mode():
            self.actions.delete.setEnabled(False)
            self.actions.copy.setEnabled(False)
            self.actions.edit.setEnabled(False)
            self.actions.shapeLineColor.setEnabled(False)
            self.actions.shapeFillColor.setEnabled(False)
            return
        if self._no_selection_slot:
            self._no_selection_slot = False
        else:
            shape = self.canvas.selected_shape
            if shape:
                self.shapes_to_items[shape].setSelected(True)
            else:
                self.label_list.clearSelection()
        self.actions.delete.setEnabled(selected)
        self.actions.copy.setEnabled(selected)
        self.actions.edit.setEnabled(selected)
        self.actions.shapeLineColor.setEnabled(selected)
        self.actions.shapeFillColor.setEnabled(selected)

    def add_label(self, shape):
        shape.paint_label = self.display_label_option.isChecked()
        item = HashableQListWidgetItem(shape.label)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        item.setBackground(generate_color_by_text(shape.label))
        self.items_to_shapes[item] = shape
        self.shapes_to_items[shape] = item
        self.label_list.addItem(item)
        for action in self.actions.onShapesPresent:
            action.setEnabled(True)
        self.update_combo_box()

    def remove_label(self, shape):
        if shape is None:
            # print('rm empty label')
            return
        item = self.shapes_to_items[shape]
        self.label_list.takeItem(self.label_list.row(item))
        del self.shapes_to_items[shape]
        del self.items_to_shapes[item]
        self.update_combo_box()

    def load_labels(self, shapes):
        s = []
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

                # Ensure the labels are within the bounds of the image. If not, fix them.
                x, y, snapped = self.canvas.snap_point_to_canvas(x, y)
                if snapped:
                    self.set_dirty()

                shape.add_point(QPointF(x, y))
            shape.difficult = difficult
            shape.close()
            s.append(shape)

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
        self.canvas.load_shapes(s)

    def update_combo_box(self):
        # Get the unique labels and add them to the Combobox.
        items_text_list = [str(self.label_list.item(i).text()) for i in range(self.label_list.count())]

        unique_text_list = list(set(items_text_list))
        # Add a null row for showing all the labels
        unique_text_list.append("")
        unique_text_list.sort()

        self.combo_box.update_items(unique_text_list)

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

        def format_shape(s):
            return dict(label=s.label,
                        line_color=s.line_color.getRgb(),
                        fill_color=s.fill_color.getRgb(),
                        points=[(p.x(), p.y()) for p in s.points],
                        is_segment=bool(getattr(s, 'is_segment', False)),
                        # add chris
                        difficult=s.difficult)

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
                self.label_file.save(annotation_file_path, shapes, self.file_path, self.image_data,
                                     self.line_color.getRgb(), self.fill_color.getRgb())
            print('Image:{0} -> Annotation:{1}'.format(self.file_path, annotation_file_path))
            return True
        except LabelFileError as e:
            self.error_message(u'Error saving label data', u'<b>%s</b>' % e)
            return False

    def copy_selected_shape(self):
        self.add_label(self.canvas.copy_selected_shape())
        # fix copy and delete
        self.shape_selection_changed(True)
        self.set_dirty()
        self._capture_history_state(clear_redo=True)

    def combo_selection_changed(self, index):
        text = self.combo_box.cb.itemText(index)
        for i in range(self.label_list.count()):
            if text == "":
                self.label_list.item(i).setCheckState(2)
            elif text != self.label_list.item(i).text():
                self.label_list.item(i).setCheckState(0)
            else:
                self.label_list.item(i).setCheckState(2)

    def default_label_combo_selection_changed(self, index):
        if 0 <= index < len(self.label_hist):
            self.default_label = self.label_hist[index]

    def label_selection_changed(self):
        if self.is_classification_mode():
            return
        item = self.current_item()
        if item and self.canvas.editing():
            self._no_selection_slot = True
            try:
                shape = self.items_to_shapes[item]
            except (KeyError, TypeError):
                return
            self.canvas.select_shape(shape)
            # Add Chris
            self.diffc_button.setChecked(shape.difficult)

    def label_item_changed(self, item):
        if self.is_classification_mode():
            return
        try:
            shape = self.items_to_shapes[item]
        except (KeyError, TypeError):
            return
        label = item.text()
        if label != shape.label:
            shape.label = item.text()
            shape.line_color = generate_color_by_text(shape.label)
            self.set_dirty()
            self._capture_history_state(clear_redo=True)
        else:  # User probably changed item visibility
            self.canvas.set_shape_visible(shape, item.checkState() == Qt.Checked)
            if not self.history_service.suppress_capture:
                self._capture_history_state(clear_redo=True)

    # Callback functions:
    def _prompt_license_plate_text(self, initial_text=''):
        text, ok = QInputDialog.getText(
            self,
            self.get_str('licensePlatePromptTitle', 'License Plate'),
            self.get_str('licensePlatePromptText', 'Enter full license plate number:'),
            text=ustr(initial_text or ''))
        if not ok:
            return None
        value = trimmed(text)
        if not value:
            self.error_message(
                self.get_str('licensePlatePromptTitle', 'License Plate'),
                self.get_str('licensePlateInvalid', 'License plate text cannot be empty.'))
            return None
        return value

    def new_shape(self):
        """Pop-up and give focus to the label editor.

        position MUST be in global coordinates.
        """
        if self.is_license_plate_mode():
            text = self._prompt_license_plate_text(self.prev_label_text)
        elif not self.use_default_label_checkbox.isChecked():
            if len(self.label_hist) > 0:
                self.label_dialog = LabelDialog(
                    parent=self, list_item=self.label_hist)

            # Sync single class mode from PR#106
            if self.single_class_mode.isChecked() and self.lastLabel:
                text = self.lastLabel
            else:
                text = self.label_dialog.pop_up(text=self.prev_label_text)
                self.lastLabel = text
        else:
            text = self.default_label

        # Add Chris
        self.diffc_button.setChecked(False)
        if text is not None:
            text = trimmed(text)
            if not self._validate_label_against_lock(text):
                self.canvas.reset_all_lines()
                return
            self.prev_label_text = text
            generate_color = generate_color_by_text(text)
            shape = self.canvas.set_last_label(text, generate_color, generate_color)
            self.add_label(shape)
            if self.beginner():  # Switch to edit mode.
                self.canvas.set_editing(True)
                self.actions.create.setEnabled(True)
            else:
                self.actions.editMode.setEnabled(True)
            self.set_dirty()
            self._capture_history_state(clear_redo=True)

            if not self.is_license_plate_mode():
                self.ensure_label_in_history(text)
        else:
            # self.canvas.undoLastLine()
            self.canvas.reset_all_lines()

    def scroll_request(self, delta, orientation):
        units = - delta / (8 * 15)
        bar = self.scroll_bars[orientation]
        bar.setValue(int(bar.value() + bar.singleStep() * units))

    def set_zoom(self, value):
        self.actions.fitWidth.setChecked(False)
        self.actions.fitWindow.setChecked(False)
        self.zoom_mode = self.MANUAL_ZOOM
        # Arithmetic on scaling factor often results in float
        # Convert to int to avoid type errors
        self.zoom_widget.setValue(int(value))

    def add_zoom(self, increment=10):
        self.set_zoom(self.zoom_widget.value() + increment)

    def zoom_request(self, delta):
        # get the current scrollbar positions
        # calculate the percentages ~ coordinates
        h_bar = self.scroll_bars[Qt.Horizontal]
        v_bar = self.scroll_bars[Qt.Vertical]

        # get the current maximum, to know the difference after zooming
        h_bar_max = h_bar.maximum()
        v_bar_max = v_bar.maximum()

        # get the cursor position and canvas size
        # calculate the desired movement from 0 to 1
        # where 0 = move left
        #       1 = move right
        # up and down analogous
        cursor = QCursor()
        pos = cursor.pos()
        relative_pos = QWidget.mapFromGlobal(self, pos)

        cursor_x = relative_pos.x()
        cursor_y = relative_pos.y()

        w = self.scroll_area.width()
        h = self.scroll_area.height()

        # the scaling from 0 to 1 has some padding
        # you don't have to hit the very leftmost pixel for a maximum-left movement
        margin = 0.1
        move_x = (cursor_x - margin * w) / (w - 2 * margin * w)
        move_y = (cursor_y - margin * h) / (h - 2 * margin * h)

        # clamp the values from 0 to 1
        move_x = min(max(move_x, 0), 1)
        move_y = min(max(move_y, 0), 1)

        # zoom in
        units = delta // (8 * 15)
        scale = 10
        self.add_zoom(scale * units)

        # get the difference in scrollbar values
        # this is how far we can move
        d_h_bar_max = h_bar.maximum() - h_bar_max
        d_v_bar_max = v_bar.maximum() - v_bar_max

        # get the new scrollbar values
        new_h_bar_value = int(h_bar.value() + move_x * d_h_bar_max)
        new_v_bar_value = int(v_bar.value() + move_y * d_v_bar_max)

        h_bar.setValue(new_h_bar_value)
        v_bar.setValue(new_v_bar_value)

    def light_request(self, delta):
        self.add_light(5*delta // (8 * 15))

    def set_fit_window(self, value=True):
        if value:
            self.actions.fitWidth.setChecked(False)
        self.zoom_mode = self.FIT_WINDOW if value else self.MANUAL_ZOOM
        self.adjust_scale()

    def set_fit_width(self, value=True):
        if value:
            self.actions.fitWindow.setChecked(False)
        self.zoom_mode = self.FIT_WIDTH if value else self.MANUAL_ZOOM
        self.adjust_scale()

    def set_light(self, value):
        self.actions.lightOrg.setChecked(int(value) == 50)
        # Arithmetic on scaling factor often results in float
        # Convert to int to avoid type errors
        self.light_widget.setValue(int(value))

    def add_light(self, increment=10):
        self.set_light(self.light_widget.value() + increment)

    def toggle_polygons(self, value):
        self.history_service.set_suppress_capture(True)
        for item, shape in self.items_to_shapes.items():
            item.setCheckState(Qt.Checked if value else Qt.Unchecked)
        self.history_service.set_suppress_capture(False)
        self._capture_history_state(clear_redo=True)

    def load_file(self, file_path=None):
        """Load the specified file, or the last opened file if None."""
        self.reset_state()
        self.canvas.setEnabled(False)
        if file_path is None:
            file_path = self.settings.get(SETTING_FILENAME)
        # Make sure that filePath is a regular python string, rather than QString
        file_path = ustr(file_path)

        # Fix bug: An  index error after select a directory when open a new file.
        unicode_file_path = ustr(file_path)
        unicode_file_path = os.path.abspath(unicode_file_path)
        # Tzutalin 20160906 : Add file list and dock to move faster
        # Highlight the file item
        if unicode_file_path and self.file_list_widget.count() > 0:
            if unicode_file_path in self.m_img_list:
                index = self.m_img_list.index(unicode_file_path)
                file_widget_item = self.file_list_widget.item(index)
                file_widget_item.setSelected(True)
            else:
                self.file_list_widget.clear()
                self.m_img_list.clear()

        if unicode_file_path and os.path.exists(unicode_file_path):
            if self.is_classification_mode():
                self.load_classification_manifest(self.dir_name or os.path.dirname(unicode_file_path))

            if not self.is_classification_mode() and LabelFile.is_label_file(unicode_file_path):
                try:
                    self.label_file = LabelFile(unicode_file_path)
                except LabelFileError as e:
                    self.error_message(u'Error opening file',
                                       (u"<p><b>%s</b></p>"
                                        u"<p>Make sure <i>%s</i> is a valid label file.")
                                       % (e, unicode_file_path))
                    self.status("Error reading %s" % unicode_file_path)
                    
                    return False
                self.image_data = self.label_file.image_data
                self.line_color = QColor(*self.label_file.lineColor)
                self.fill_color = QColor(*self.label_file.fillColor)
                self.canvas.verified = self.label_file.verified
            else:
                # Load image:
                # read data first and store for saving into label file.
                self.image_data = read(unicode_file_path, None)
                self.label_file = None
                self.canvas.verified = False

            if isinstance(self.image_data, QImage):
                image = self.image_data
            else:
                image = QImage.fromData(self.image_data)
            if image.isNull():
                self.error_message(u'Error opening file',
                                   u"<p>Make sure <i>%s</i> is a valid image file." % unicode_file_path)
                self.status("Error reading %s" % unicode_file_path)
                return False
            self.status("Loaded %s" % os.path.basename(unicode_file_path))
            self.image = image
            self.file_path = unicode_file_path
            self.canvas.load_pixmap(QPixmap.fromImage(image))
            if self.label_file and not self.is_classification_mode():
                self.load_labels(self.label_file.shapes)
            self.set_clean()
            self.canvas.setEnabled(True)
            self.adjust_scale(initial=True)
            self.paint_canvas()
            self.add_recent_file(self.file_path)
            self.toggle_actions(True)
            if not self.is_classification_mode():
                self.show_bounding_box_from_annotation_file(self.file_path)
            else:
                self.update_classification_ui()

            self.update_image_counter_display()
            self.setWindowTitle(__appname__)

            # Default : select last item if there is at least one item
            if self.label_list.count() and not self.is_classification_mode():
                self.label_list.setCurrentItem(self.label_list.item(self.label_list.count() - 1))
                self.label_list.item(self.label_list.count() - 1).setSelected(True)

            self.canvas.setFocus(True)
            self._initialize_annotation_history()
            return True
        return False

    def counter_str(self):
        """
        Converts image counter to string representation.
        """
        return '[{} / {}]'.format(self.cur_img_idx + 1, self.img_count)

    def show_bounding_box_from_annotation_file(self, file_path):
        if self.is_classification_mode():
            return
        if not file_path:
            return
        if self.default_save_dir is not None:
            basename = os.path.basename(os.path.splitext(file_path)[0])
            xml_path = os.path.join(self.default_save_dir, basename + XML_EXT)
            txt_path = os.path.join(self.default_save_dir, basename + TXT_EXT)
            json_path = os.path.join(self.default_save_dir, basename + JSON_EXT)

            if self.is_license_plate_mode():
                if os.path.isfile(txt_path):
                    self.load_license_plate_txt_by_filename(txt_path)
                return

            """Annotation file priority:
            PascalXML > YOLO
            """
            if os.path.isfile(xml_path):
                self.load_pascal_xml_by_filename(xml_path)
            elif os.path.isfile(txt_path):
                self.load_yolo_txt_by_filename(txt_path)
            elif os.path.isfile(json_path):
                self.load_create_ml_json_by_filename(json_path, file_path)

        else:
            xml_path = os.path.splitext(file_path)[0] + XML_EXT
            txt_path = os.path.splitext(file_path)[0] + TXT_EXT
            json_path = os.path.splitext(file_path)[0] + JSON_EXT

            if self.is_license_plate_mode():
                if os.path.isfile(txt_path):
                    self.load_license_plate_txt_by_filename(txt_path)
                return

            if os.path.isfile(xml_path):
                self.load_pascal_xml_by_filename(xml_path)
            elif os.path.isfile(txt_path):
                self.load_yolo_txt_by_filename(txt_path)
            elif os.path.isfile(json_path):
                self.load_create_ml_json_by_filename(json_path, file_path)
            

    def resizeEvent(self, event):
        if self.canvas and not self.image.isNull()\
           and self.zoom_mode != self.MANUAL_ZOOM:
            self.adjust_scale()
        super(MainWindow, self).resizeEvent(event)

    def paint_canvas(self):
        # valueChanged callbacks can fire during startup/reset before an image is loaded.
        # Treat that as a no-op instead of aborting the app.
        if self.image.isNull():
            return
        self.canvas.scale = 0.01 * self.zoom_widget.value()
        self.canvas.overlay_color = self.light_widget.color()
        self.canvas.label_font_size = int(0.02 * max(self.image.width(), self.image.height()))
        self.canvas.adjustSize()
        self.canvas.update()

    def adjust_scale(self, initial=False):
        value = self.scalers[self.FIT_WINDOW if initial else self.zoom_mode]()
        self.zoom_widget.setValue(int(100 * value))

    def scale_fit_window(self):
        """Figure out the size of the pixmap in order to fit the main widget."""
        e = 2.0  # So that no scrollbars are generated.
        w1 = self.centralWidget().width() - e
        h1 = self.centralWidget().height() - e
        a1 = w1 / h1
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def scale_fit_width(self):
        # The epsilon does not seem to work too well here.
        w = self.centralWidget().width() - 2.0
        return w / self.canvas.pixmap.width()

    def closeEvent(self, event):
        if self.training_running and self.training_worker is not None:
            should_stop = QMessageBox.question(
                self,
                'Train YOLOv8',
                'Training is still running. Stop training and close Labellix Studio?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No)
            if should_stop != QMessageBox.Yes:
                event.ignore()
                return
            self.training_worker.stop()
            if not self.training_worker.wait(5000):
                QMessageBox.warning(
                    self,
                    'Train YOLOv8',
                    'Could not stop training process cleanly. Please wait a moment and try closing again.')
                event.ignore()
                return

        if not self.may_continue():
            event.ignore()
            return
        settings = self.settings
        settings[SETTING_FILENAME] = self.file_path if self.file_path else ''

        settings[SETTING_WIN_SIZE] = self.size()
        settings[SETTING_WIN_POSE] = self.pos()
        settings[SETTING_WIN_STATE] = self.saveState()
        settings[SETTING_LINE_COLOR] = self.line_color
        settings[SETTING_FILL_COLOR] = self.fill_color
        settings[SETTING_RECENT_FILES] = self.recent_files
        settings[SETTING_ADVANCE_MODE] = not self._beginner
        if self.default_save_dir and os.path.exists(self.default_save_dir):
            settings[SETTING_SAVE_DIR] = ustr(self.default_save_dir)
        else:
            settings[SETTING_SAVE_DIR] = ''

        if self.last_open_dir and os.path.exists(self.last_open_dir):
            settings[SETTING_LAST_OPEN_DIR] = self.last_open_dir
        else:
            settings[SETTING_LAST_OPEN_DIR] = ''

        settings[SETTING_AUTO_SAVE] = self.auto_saving.isChecked()
        settings[SETTING_AUTO_NEXT_ON_SAVE] = self.auto_next_on_save.isChecked()
        settings[SETTING_SINGLE_CLASS] = self.single_class_mode.isChecked()
        settings[SETTING_PAINT_LABEL] = self.display_label_option.isChecked()
        settings[SETTING_COMPACT_MODE] = self.compact_mode_option.isChecked()
        settings[SETTING_MODERN_ICONS] = self.modern_icons_option.isChecked()
        settings[SETTING_REDUCED_MOTION] = self.reduced_motion_option.isChecked()
        settings[SETTING_LOCK_PREDEFINED_CLASSES] = self.lock_predefined_classes_checkbox.isChecked()
        settings[SETTING_FOCUS_MODE] = self.focus_mode_option.isChecked()
        settings[SETTING_DRAW_SQUARE] = self.draw_squares_option.isChecked()
        settings[SETTING_LABEL_FILE_FORMAT] = self.label_file_format
        settings[SETTING_APP_MODE] = self.app_mode
        settings[SETTING_CLASSIFICATION_EXPORT_DIR] = self.classification_export_dir
        settings[SETTING_LICENSE_PLATE_EXPORT_DIR] = self.license_plate_export_dir
        settings[SETTING_YOLO_EXPORT_DIR] = self.yolo_export_dir
        settings[SETTING_YOLO_LAST_DATASET_YAML] = self.last_exported_dataset_yaml
        settings[SETTING_RESUME_IMAGE_INDEX] = self.cur_img_idx
        settings[SETTING_RESUME_ZOOM] = self.zoom_widget.value()
        settings.save()

    def load_recent(self, filename):
        if self.may_continue():
            self.load_file(filename)

    def scan_all_images(self, folder_path):
        extensions = ['.%s' % fmt.data().decode("ascii").lower() for fmt in QImageReader.supportedImageFormats()]
        images = []

        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(tuple(extensions)):
                    relative_path = os.path.join(root, file)
                    path = ustr(os.path.abspath(relative_path))
                    images.append(path)
        natural_sort(images, key=lambda x: x.lower())
        return images

    def change_save_dir_dialog(self, _value=False):
        if self.default_save_dir is not None:
            path = ustr(self.default_save_dir)
        else:
            path = '.'

        dir_path = ustr(QFileDialog.getExistingDirectory(self,
                                                         '%s - Save annotations to the directory' % __appname__, path,  QFileDialog.ShowDirsOnly
                                                         | QFileDialog.DontResolveSymlinks))

        if dir_path is not None and len(dir_path) > 1:
            self.default_save_dir = dir_path

        if self.file_path:
            self.show_bounding_box_from_annotation_file(self.file_path)

        self.statusBar().showMessage('%s . Annotation will be saved to %s' %
                                     ('Change saved folder', self.default_save_dir))
        self.statusBar().show()


    def open_annotation_dialog(self, _value=False):
        if self.file_path is None:
            self.statusBar().showMessage('Please select image first')
            self.statusBar().show()
            return

        path = os.path.dirname(ustr(self.file_path))\
            if self.file_path else '.'
        if self.label_file_format == LabelFileFormat.PASCAL_VOC:
            filters = "Open Annotation XML file (%s)" % ' '.join(['*.xml'])
            filename = ustr(QFileDialog.getOpenFileName(self, '%s - Choose a xml file' % __appname__, path, filters))
            if filename:
                if isinstance(filename, (tuple, list)):
                    filename = filename[0]
            self.load_pascal_xml_by_filename(filename)

        elif self.label_file_format == LabelFileFormat.CREATE_ML:
            
            filters = "Open Annotation JSON file (%s)" % ' '.join(['*.json'])
            filename = ustr(QFileDialog.getOpenFileName(self, '%s - Choose a json file' % __appname__, path, filters))
            if filename:
                if isinstance(filename, (tuple, list)):
                    filename = filename[0]

            self.load_create_ml_json_by_filename(filename, self.file_path)         
        

    def open_dir_dialog(self, _value=False, dir_path=None, silent=False):
        if not self.may_continue():
            return

        default_open_dir_path = dir_path if dir_path else '.'
        if self.last_open_dir and os.path.exists(self.last_open_dir):
            default_open_dir_path = self.last_open_dir
        else:
            default_open_dir_path = os.path.dirname(self.file_path) if self.file_path else '.'
        if silent != True:
            image_formats = ['*.%s' % fmt.data().decode('ascii').lower() for fmt in QImageReader.supportedImageFormats()]
            filters = 'Image files (%s);;All files (*)' % ' '.join(image_formats)
            selected_file, _selected_filter = QFileDialog.getOpenFileName(
                self,
                '%s - Open Directory' % __appname__,
                default_open_dir_path,
                filters,
            )
            selected_file = ustr(selected_file)
            if not selected_file:
                return
            target_dir_path = selected_file if os.path.isdir(selected_file) else os.path.dirname(selected_file)
        else:
            target_dir_path = ustr(default_open_dir_path)
        if not target_dir_path:
            return
        self.last_open_dir = target_dir_path
        self.import_dir_images(target_dir_path)
        self.default_save_dir = target_dir_path
        if self.file_path:
            self.show_bounding_box_from_annotation_file(file_path=self.file_path)

    def import_dir_images(self, dir_path):
        if not self.may_continue() or not dir_path:
            return

        self.last_open_dir = dir_path
        self.dir_name = dir_path
        self.file_path = None
        self.file_list_widget.clear()
        self.m_img_list = self.scan_all_images(dir_path)
        self.img_count = len(self.m_img_list)
        for imgPath in self.m_img_list:
            item = QListWidgetItem(imgPath)
            self.file_list_widget.addItem(item)
        if self.img_count == 0:
            # Clear any previously loaded image so the canvas does not show stale content.
            self.reset_state()
            self.set_clean()
            self.toggle_actions(False)
            self.canvas.setEnabled(False)
            self.actions.saveAs.setEnabled(False)
            return
        if self.is_classification_mode():
            self.load_classification_manifest(dir_path)
        self.refresh_file_list_classification_state()
        resume_file = ustr(self.settings.get(SETTING_FILENAME, ''))
        resume_index = self.settings.get(SETTING_RESUME_IMAGE_INDEX, 0)
        try:
            resume_index = int(resume_index)
        except (TypeError, ValueError):
            resume_index = 0
        if resume_file and resume_file in self.m_img_list:
            self.cur_img_idx = self.m_img_list.index(resume_file)
            self.load_file(resume_file)
        elif 0 <= resume_index < self.img_count:
            self.cur_img_idx = resume_index
            self.load_file(self.m_img_list[self.cur_img_idx])
        else:
            self.open_next_image()

    def verify_image(self, _value=False):
        # Proceeding next image without dialog if having any label
        if self.file_path is not None:
            try:
                self.label_file.toggle_verify()
            except AttributeError:
                # If the labelling file does not exist yet, create if and
                # re-save it with the verified attribute.
                self.save_file()
                if self.label_file is not None:
                    self.label_file.toggle_verify()
                else:
                    return

            self.canvas.verified = self.label_file.verified
            self.paint_canvas()
            self.save_file()

    def open_prev_image(self, _value=False):
        # Proceeding prev image without dialog if having any label
        if self.is_classification_mode() and self.dirty:
            if not self.save_file():
                return
        elif self.auto_saving.isChecked():
            if self.default_save_dir is not None:
                if self.dirty is True:
                    self.save_file()
            else:
                self.change_save_dir_dialog()
                return

        if not self.may_continue():
            return

        if self.img_count <= 0:
            return

        if self.file_path is None:
            return

        if self.cur_img_idx - 1 >= 0:
            self.cur_img_idx -= 1
            filename = self.m_img_list[self.cur_img_idx]
            if filename:
                self.load_file(filename)

    def open_next_image(self, _value=False):
        # Proceeding next image without dialog if having any label
        if self.is_classification_mode() and self.dirty:
            if not self.save_file():
                return
        elif self.auto_saving.isChecked():
            if self.default_save_dir is not None:
                if self.dirty is True:
                    self.save_file()
            else:
                self.change_save_dir_dialog()
                return

        if not self.may_continue():
            return

        if self.img_count <= 0:
            return
        
        if not self.m_img_list:
            return

        filename = None
        if self.file_path is None:
            filename = self.m_img_list[0]
            self.cur_img_idx = 0
        else:
            if self.cur_img_idx + 1 < self.img_count:
                self.cur_img_idx += 1
                filename = self.m_img_list[self.cur_img_idx]

        if filename:
            self.load_file(filename)

    def open_file(self, _value=False):
        if not self.may_continue():
            return
        path = os.path.dirname(ustr(self.file_path)) if self.file_path else '.'
        formats = ['*.%s' % fmt.data().decode("ascii").lower() for fmt in QImageReader.supportedImageFormats()]
        filter_parts = list(formats)
        if self.is_license_plate_mode():
            filter_parts.append('*%s' % TXT_EXT)
        elif not self.is_classification_mode():
            filter_parts.append('*%s' % LabelFile.suffix)
        filters = "Image & Label files (%s)" % ' '.join(filter_parts)
        filename,_ = QFileDialog.getOpenFileName(self, '%s - Choose Image or Label file' % __appname__, path, filters)
        if filename:
            if isinstance(filename, (tuple, list)):
                filename = filename[0]
            self.cur_img_idx = 0
            self.img_count = 1
            self.load_file(filename)

    def save_file(self, _value=False):
        if self.is_classification_mode():
            saved = self.save_classification_manifest()
            if saved and self.auto_next_on_save.isChecked():
                self.open_next_image()
            return saved
        if not self.file_path:
            self.statusBar().showMessage('Please select image first')
            self.statusBar().show()
            return False
        saved = False
        if self.default_save_dir is not None and len(ustr(self.default_save_dir)):
            if self.file_path:
                image_file_name = os.path.basename(self.file_path)
                saved_file_name = os.path.splitext(image_file_name)[0]
                saved_path = os.path.join(ustr(self.default_save_dir), saved_file_name)
                saved = self._save_file(saved_path)
        else:
            image_file_dir = os.path.dirname(self.file_path)
            image_file_name = os.path.basename(self.file_path)
            saved_file_name = os.path.splitext(image_file_name)[0]
            saved_path = os.path.join(image_file_dir, saved_file_name)
            saved = self._save_file(saved_path if self.label_file
                                    else self.save_file_dialog(remove_ext=False))

        if saved and self.auto_next_on_save.isChecked():
            self.open_next_image()
        return saved

    def save_file_as(self, _value=False):
        assert not self.image.isNull(), "cannot save empty image"
        self._save_file(self.save_file_dialog())

    def save_file_dialog(self, remove_ext=True):
        caption = '%s - Choose File' % __appname__
        filters = 'File (*%s)' % (TXT_EXT if self.is_license_plate_mode() else LabelFile.suffix)
        open_dialog_path = self.current_path()
        dlg = QFileDialog(self, caption, open_dialog_path, filters)
        default_suffix = TXT_EXT[1:] if self.is_license_plate_mode() else LabelFile.suffix[1:]
        dlg.setDefaultSuffix(default_suffix)
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        filename_without_extension = os.path.splitext(self.file_path)[0] if self.file_path else ''
        dlg.selectFile(filename_without_extension)
        dlg.setOption(QFileDialog.DontUseNativeDialog, False)
        if dlg.exec_():
            full_file_path = ustr(dlg.selectedFiles()[0])
            if remove_ext:
                return os.path.splitext(full_file_path)[0]  # Return file path without the extension.
            else:
                return full_file_path
        return ''

    def _save_file(self, annotation_file_path):
        if annotation_file_path and self.save_labels(annotation_file_path):
            self.set_clean()
            self.statusBar().showMessage('Saved to  %s' % annotation_file_path)
            self.statusBar().show()
            return True
        return False

    def close_file(self, _value=False):
        if not self.may_continue():
            return
        self.reset_state()
        self.set_clean()
        self.toggle_actions(False)
        self.canvas.setEnabled(False)
        self.actions.saveAs.setEnabled(False)
        self.update_classification_ui()

    def _ensure_trash_dir(self, source_path):
        trash_dir = os.path.join(os.path.dirname(source_path), '.labellix_trash')
        if not os.path.exists(trash_dir):
            os.makedirs(trash_dir)
        return trash_dir

    def _move_file_to_trash(self, source_path):
        trash_dir = self._ensure_trash_dir(source_path)
        filename = os.path.basename(source_path)
        stem, ext = os.path.splitext(filename)
        timestamp = time.strftime('%Y%m%d-%H%M%S')
        candidate = os.path.join(trash_dir, '%s_%s%s' % (stem, timestamp, ext))
        suffix = 1
        while os.path.exists(candidate):
            candidate = os.path.join(trash_dir, '%s_%s_%d%s' % (stem, timestamp, suffix, ext))
            suffix += 1
        shutil.move(source_path, candidate)
        return candidate

    def delete_image(self):
        delete_path = self.file_path
        if delete_path is None:
            return

        if not os.path.exists(delete_path):
            self.error_message('Delete image failed', 'Image file does not exist: %s' % delete_path)
            return

        prompt = (
            'Move this image to .labellix_trash?\n\n'
            'File: %s\n\n'
            'You can manually restore it from the trash folder if needed.'
        ) % delete_path
        decision = QMessageBox.warning(self, 'Delete Image', prompt, QMessageBox.Yes | QMessageBox.No)
        if decision != QMessageBox.Yes:
            return

        idx = self.cur_img_idx
        try:
            trashed_path = self._move_file_to_trash(delete_path)
            self.status('Moved image to trash: %s' % trashed_path)
        except OSError as exc:
            self.error_message('Delete image failed', 'Could not move image to trash:\n%s' % exc)
            return

        self.import_dir_images(self.last_open_dir)
        if self.img_count > 0:
            self.cur_img_idx = min(idx, self.img_count - 1)
            filename = self.m_img_list[self.cur_img_idx]
            self.load_file(filename)
        else:
            self.close_file()

    def reset_all(self):
        self.settings.reset()
        self.close()
        process = QProcess()
        process.startDetached(os.path.abspath(__file__))

    def may_continue(self):
        if not self.dirty:
            return True
        else:
            discard_changes = self.discard_changes_dialog()
            if discard_changes == QMessageBox.No:
                return True
            elif discard_changes == QMessageBox.Yes:
                self.save_file()
                return True
            else:
                return False

    def discard_changes_dialog(self):
        yes, no, cancel = QMessageBox.Yes, QMessageBox.No, QMessageBox.Cancel
        msg = u'You have unsaved changes, would you like to save them and proceed?\nClick "No" to undo all changes.'
        return QMessageBox.warning(self, u'Attention', msg, yes | no | cancel)

    def error_message(self, title, message):
        return QMessageBox.critical(self, title,
                                    '<p><b>%s</b></p>%s' % (title, message))

    def current_path(self):
        return os.path.dirname(self.file_path) if self.file_path else '.'

    def choose_color1(self):
        color = self.color_dialog.getColor(self.line_color, u'Choose line color',
                                           default=DEFAULT_LINE_COLOR)
        if color:
            self.line_color = color
            Shape.line_color = color
            self.canvas.set_drawing_color(color)
            self.canvas.update()
            self.set_dirty()

    def delete_selected_shape(self):
        self.remove_label(self.canvas.delete_selected())
        self.set_dirty()
        self._capture_history_state(clear_redo=True)
        if self.no_shapes():
            for action in self.actions.onShapesPresent:
                action.setEnabled(False)

    def choose_shape_line_color(self):
        color = self.color_dialog.getColor(self.line_color, u'Choose Line Color',
                                           default=DEFAULT_LINE_COLOR)
        if color:
            self.canvas.selected_shape.line_color = color
            self.canvas.update()
            self.set_dirty()
            self._capture_history_state(clear_redo=True)

    def choose_shape_fill_color(self):
        color = self.color_dialog.getColor(self.fill_color, u'Choose Fill Color',
                                           default=DEFAULT_FILL_COLOR)
        if color:
            self.canvas.selected_shape.fill_color = color
            self.canvas.update()
            self.set_dirty()
            self._capture_history_state(clear_redo=True)

    def copy_shape(self):
        if self.canvas.selected_shape is None:
            # True if one accidentally touches the left mouse button before releasing
            return
        self.canvas.end_move(copy=True)
        self.add_label(self.canvas.selected_shape)
        self.set_dirty()
        self._capture_history_state(clear_redo=True)

    def move_shape(self):
        self.canvas.end_move(copy=False)
        self.set_dirty()
        self._capture_history_state(clear_redo=True)

    def load_predefined_classes(self, predef_classes_file):
        if not predef_classes_file:
            return

        predef_classes_file = ustr(predef_classes_file)
        self.predefined_classes_file = predef_classes_file
        self.label_hist.extend(self._read_predefined_classes_file())

    def _read_predefined_classes_file(self):
        predef_classes_file = ustr(getattr(self, 'predefined_classes_file', '') or '')
        if not predef_classes_file:
            return []

        predef_dir = os.path.dirname(predef_classes_file)
        if predef_dir and (not os.path.isdir(predef_dir)):
            os.makedirs(predef_dir)

        if not os.path.exists(predef_classes_file):
            with codecs.open(predef_classes_file, 'w', 'utf8'):
                pass
            print(self.get_str('predefinedClassesCreated', 'Created missing predefined classes file: %s') % predef_classes_file)

        labels = []
        with codecs.open(predef_classes_file, 'r', 'utf8') as f:
            seen = set()
            for line in f:
                line = trimmed(line)
                if not line or line in seen:
                    continue
                seen.add(line)
                labels.append(line)
        return labels

    def load_pascal_xml_by_filename(self, xml_path):
        if self.file_path is None:
            return
        if os.path.isfile(xml_path) is False:
            return

        adapter = self.annotation_io.get_by_format(LabelFileFormat.PASCAL_VOC)
        self.set_format(adapter.save_format)
        shapes, verified = adapter.load(xml_path, self.image, self.file_path)
        self.load_labels(shapes)
        self.canvas.verified = verified

    def load_yolo_txt_by_filename(self, txt_path):
        if self.file_path is None:
            return
        if os.path.isfile(txt_path) is False:
            return

        adapter = self.annotation_io.get_by_format(LabelFileFormat.YOLO)
        self.set_format(adapter.save_format)
        shapes, verified = adapter.load(txt_path, self.image, self.file_path)
        self.load_labels(shapes)
        self.canvas.verified = verified

    def load_license_plate_txt_by_filename(self, txt_path):
        if self.file_path is None:
            return
        if os.path.isfile(txt_path) is False:
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
        if os.path.isfile(json_path) is False:
            return

        adapter = self.annotation_io.get_by_format(LabelFileFormat.CREATE_ML)
        self.set_format(adapter.save_format)
        shapes, verified = adapter.load(json_path, self.image, file_path)
        self.load_labels(shapes)
        self.canvas.verified = verified

    def copy_previous_bounding_boxes(self):
        current_index = self.m_img_list.index(self.file_path)
        if current_index - 1 >= 0:
            prev_file_path = self.m_img_list[current_index - 1]
            self.show_bounding_box_from_annotation_file(prev_file_path)
            self.save_file()

    def toggle_paint_labels_option(self):
        for shape in self.canvas.shapes:
            shape.paint_label = self.display_label_option.isChecked()

    def toggle_draw_square(self):
        self.canvas.set_drawing_shape_to_square(self.draw_squares_option.isChecked())
        self.update_shortcut_hints()

def inverted(color):
    return QColor(*[255 - v for v in color.getRgb()])


def read(filename, default=None):
    try:
        reader = QImageReader(filename)
        reader.setAutoTransform(True)
        return reader.read()
    except Exception:
        return default


def get_main_app(argv=None):
    """
    Standard boilerplate Qt application code.
    Do everything but app.exec_() -- so that we can test the application in one thread
    """
    if not argv:
        argv = []
    app = QApplication(argv)
    app.setApplicationName(__appname__)
    app_icon = build_app_icon()
    app_icon_path = get_primary_app_icon_path()
    ensure_linux_desktop_entry(app_icon_path)
    QApplication.setWindowIcon(app_icon)
    app.setWindowIcon(app_icon)
    if hasattr(app, 'setDesktopFileName'):
        app.setDesktopFileName('labellix-studio')
    # Tzutalin 201705+: Accept extra agruments to change predefined class file
    argparser = argparse.ArgumentParser()
    argparser.add_argument("image_dir", nargs="?")
    argparser.add_argument("class_file",
                           default=os.path.join(os.path.dirname(__file__), "data", "predefined_classes.txt"),
                           nargs="?")
    argparser.add_argument("save_dir", nargs="?")
    args = argparser.parse_args(argv[1:])

    args.image_dir = args.image_dir and os.path.normpath(args.image_dir)
    args.class_file = args.class_file and os.path.normpath(args.class_file)
    args.save_dir = args.save_dir and os.path.normpath(args.save_dir)

    # Usage: launch Labellix Studio with optional image/class/save-dir arguments.
    win = MainWindow(args.image_dir,
                     args.class_file,
                     args.save_dir)
    win.show()
    return app, win


def main():
    """construct main app and run it"""
    app, _win = get_main_app(sys.argv)
    return app.exec_()

if __name__ == '__main__':
    sys.exit(main())
