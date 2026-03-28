try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import QColorDialog, QDialogButtonBox, QGraphicsOpacityEffect
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

from libs.utils import new_icon

BB = QDialogButtonBox


class ColorDialog(QColorDialog):

    def __init__(self, parent=None):
        super(ColorDialog, self).__init__(parent)
        self.setOption(QColorDialog.ShowAlphaChannel)
        # The Mac native dialog does not support our restore button.
        self.setOption(QColorDialog.DontUseNativeDialog)
        # Add a restore defaults button.
        # The default is set at invocation time, so that it
        # works across dialogs for different elements.
        self.default = None
        self.bb = self.layout().itemAt(1).widget()
        self.bb.addButton(BB.RestoreDefaults)
        restore_btn = self.bb.button(BB.RestoreDefaults)
        if restore_btn is not None:
            restore_btn.setIcon(new_icon('light_reset'))
            restore_btn.setObjectName('restoreDefaultBtn')
        self.bb.clicked.connect(self.check_restore)

    def getColor(self, value=None, title=None, default=None):
        self.default = default
        if title:
            self.setWindowTitle(title)
        if value:
            self.setCurrentColor(value)
        parent = self.parentWidget()
        if not (parent is not None and bool(getattr(parent, 'reduced_motion', False))):
            effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(effect)
            self._entry_anim = QPropertyAnimation(effect, b'opacity', self)
            self._entry_anim.setDuration(150)
            self._entry_anim.setStartValue(0.0)
            self._entry_anim.setEndValue(1.0)
            QTimer.singleShot(0, self._entry_anim.start)
        return self.currentColor() if self.exec_() else None

    def check_restore(self, button):
        if self.bb.buttonRole(button) & BB.ResetRole and self.default:
            self.setCurrentColor(self.default)
