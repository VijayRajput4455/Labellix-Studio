from math import sqrt
from libs.ustr import ustr
import hashlib
import os
import re
import sys

try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
    QT5 = True
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *
    QT5 = False


class _IconPreferences(object):

    def __init__(self):
        self.use_modern_svg_icons = True
        self.use_native_icons = True
        self.use_theme_icons = True
        self.icon_tint_color = None

    def update(self, use_modern_svg=True, use_native=True, use_theme=True, tint_color=None):
        self.use_modern_svg_icons = bool(use_modern_svg)
        self.use_native_icons = bool(use_native)
        self.use_theme_icons = bool(use_theme)
        self.icon_tint_color = tint_color


_ICON_PREFERENCES = _IconPreferences()


def get_icon_preferences():
    """Return a snapshot of icon preferences.

    This avoids exposing mutable module state directly.
    """
    return {
        'use_modern_svg_icons': _ICON_PREFERENCES.use_modern_svg_icons,
        'use_native_icons': _ICON_PREFERENCES.use_native_icons,
        'use_theme_icons': _ICON_PREFERENCES.use_theme_icons,
        'icon_tint_color': _ICON_PREFERENCES.icon_tint_color,
    }


def set_icon_preferences(use_modern_svg=True, use_native=True, use_theme=True, tint_color=None):
    _ICON_PREFERENCES.update(
        use_modern_svg=use_modern_svg,
        use_native=use_native,
        use_theme=use_theme,
        tint_color=tint_color,
    )


def _apply_icon_tint(icon):
    tint_color = _ICON_PREFERENCES.icon_tint_color
    if not tint_color:
        return icon

    tint = QColor(tint_color)
    if not tint.isValid():
        return icon

    tinted_icon = QIcon()
    sizes = [14, 16, 18, 20, 22, 24, 28, 32]
    for size in sizes:
        src = icon.pixmap(size, size)
        if src.isNull():
            continue
        dst = QPixmap(src.size())
        dst.fill(Qt.transparent)
        painter = QPainter(dst)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.drawPixmap(0, 0, src)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(dst.rect(), tint)
        painter.end()
        tinted_icon.addPixmap(dst)

    if tinted_icon.isNull():
        return icon
    return tinted_icon


def new_icon(icon):
    # Prefer modern bundled SVG assets when present.
    if _ICON_PREFERENCES.use_modern_svg_icons:
        modern_svg = os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..', 'resources', 'icons', 'modern', '%s.svg' % icon))
        if os.path.exists(modern_svg):
            svg_icon = QIcon(modern_svg)
            if svg_icon and (not svg_icon.isNull()):
                return _apply_icon_tint(svg_icon)

    # Prefer desktop-native icons when available, then fall back to bundled resources.
    app = QApplication.instance()
    if _ICON_PREFERENCES.use_native_icons and app is not None:
        style = app.style()
        if style is not None:
            standard_map = {
                'open': getattr(QStyle, 'SP_DialogOpenButton', None),
                'save': getattr(QStyle, 'SP_DialogSaveButton', None),
                'save-as': getattr(QStyle, 'SP_DialogSaveButton', None),
                'close': getattr(QStyle, 'SP_DialogCloseButton', None),
                'quit': getattr(QStyle, 'SP_DialogCloseButton', None),
                'undo': getattr(QStyle, 'SP_ArrowBack', None),
                'redo': getattr(QStyle, 'SP_ArrowForward', None),
                'next': getattr(QStyle, 'SP_ArrowForward', None),
                'prev': getattr(QStyle, 'SP_ArrowBack', None),
                'help': getattr(QStyle, 'SP_DialogHelpButton', None),
                'delete': getattr(QStyle, 'SP_TrashIcon', None),
                'verify': getattr(QStyle, 'SP_DialogApplyButton', None),
                'zoom-in': getattr(QStyle, 'SP_ArrowUp', None),
                'zoom-out': getattr(QStyle, 'SP_ArrowDown', None),
            }
            pixmap_type = standard_map.get(icon)
            if pixmap_type is not None:
                native_icon = style.standardIcon(pixmap_type)
                if native_icon and (not native_icon.isNull()):
                    return native_icon

    if _ICON_PREFERENCES.use_theme_icons:
        themed_icon = QIcon.fromTheme(icon)
        if themed_icon and (not themed_icon.isNull()):
            return themed_icon

    return _apply_icon_tint(QIcon(':/' + icon))


def new_button(text, icon=None, slot=None):
    b = QPushButton(text)
    if icon is not None:
        b.setIcon(new_icon(icon))
    if slot is not None:
        b.clicked.connect(slot)
    return b


def new_action(parent, text, slot=None, shortcut=None, icon=None,
               tip=None, checkable=False, enabled=True):
    """Create a new action and assign callbacks, shortcuts, etc."""
    a = QAction(text, parent)
    if icon is not None:
        a.setProperty('iconName', icon)
        a.setIcon(new_icon(icon))
    if shortcut is not None:
        if isinstance(shortcut, (list, tuple)):
            a.setShortcuts(shortcut)
        else:
            a.setShortcut(shortcut)
    if tip is not None:
        a.setToolTip(tip)
        a.setStatusTip(tip)
    if slot is not None:
        a.triggered.connect(slot)
    if checkable:
        a.setCheckable(True)
    a.setEnabled(enabled)
    return a


def add_actions(widget, actions):
    for action in actions:
        if action is None:
            widget.addSeparator()
        elif isinstance(action, QMenu):
            widget.addMenu(action)
        else:
            widget.addAction(action)


def label_validator():
    return QRegExpValidator(QRegExp(r'^[^ \t].+'), None)


class Struct(object):

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def distance(p):
    return sqrt(p.x() * p.x() + p.y() * p.y())


def format_shortcut(text):
    mod, key = text.split('+', 1)
    return '<b>%s</b>+<b>%s</b>' % (mod, key)


def generate_color_by_text(text):
    s = ustr(text)
    hash_code = int(hashlib.sha256(s.encode('utf-8')).hexdigest(), 16)
    r = int((hash_code / 255) % 255)
    g = int((hash_code / 65025) % 255)
    b = int((hash_code / 16581375) % 255)
    return QColor(r, g, b, 100)


def have_qstring():
    """p3/qt5 get rid of QString wrapper as py3 has native unicode str type"""
    return not (sys.version_info.major >= 3 or QT_VERSION_STR.startswith('5.'))


def util_qt_strlistclass():
    return QStringList if have_qstring() else list


def natural_sort(list, key=lambda s:s):
    """
    Sort the list into natural alphanumeric order.
    """
    def get_alphanum_key_func(key):
        convert = lambda text: int(text) if text.isdigit() else text
        return lambda s: [convert(c) for c in re.split('([0-9]+)', key(s))]
    sort_key = get_alphanum_key_func(key)
    list.sort(key=sort_key)


# QT4 has a trimmed method, in QT5 this is called strip
if QT5:
    def trimmed(text):
        return text.strip()
else:
    def trimmed(text):
        return text.trimmed()
