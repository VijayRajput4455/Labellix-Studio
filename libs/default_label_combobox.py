import sys
try:
    from PyQt5.QtWidgets import QWidget, QHBoxLayout, QComboBox, QSizePolicy, QLabel
except ImportError:
    # needed for py3+qt4
    # Ref:
    # http://pyqt.sourceforge.net/Docs/PyQt4/incompatible_apis.html
    # http://stackoverflow.com/questions/21217399/pyqt4-qtcore-qvariant-object-instead-of-a-string
    if sys.version_info.major >= 3:
        import sip
        sip.setapi('QVariant', 2)
    from PyQt4.QtGui import QWidget, QHBoxLayout, QComboBox, QSizePolicy, QLabel

from libs.utils import new_icon


class DefaultLabelComboBox(QWidget):
    def __init__(self, parent=None, items=[]):
        super(DefaultLabelComboBox, self).__init__(parent)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.setObjectName('defaultLabelContainer')
        self.icon_label = QLabel()
        self.icon_label.setObjectName('defaultLabelIcon')
        self.icon_label.setPixmap(new_icon('labels').pixmap(16, 16))
        self.cb = QComboBox()
        self.cb.setObjectName('defaultLabelCombo')
        self.cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.items = items
        self.cb.addItems(self.items)

        self.cb.currentIndexChanged.connect(parent.default_label_combo_selection_changed)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.cb)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def refresh_icon(self):
        self.icon_label.setPixmap(new_icon('labels').pixmap(16, 16))
