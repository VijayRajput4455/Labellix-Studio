try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *


class ToolBar(QToolBar):

    def __init__(self, title):
        super(ToolBar, self).__init__(title)
        self.setObjectName('customToolBar')
        self._tool_button_style = Qt.ToolButtonTextUnderIcon
        self._buttons = []
        self._item_width = 122

        layout = self.layout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setContentsMargins(0, 0, 0, 0)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setMovable(False)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self._scroll_area.setFrameShape(QFrame.NoFrame)
        self._scroll_area.setFocusPolicy(Qt.StrongFocus)

        content_width = 150
        self._scroll_area.setMinimumWidth(content_width)
        self.setMinimumWidth(content_width)

        self._v_scrollbar = self._scroll_area.verticalScrollBar()
        self._v_scrollbar.setObjectName('toolBarScrollBar')
        self._v_scrollbar.setSingleStep(24)
        self._v_scrollbar.setPageStep(120)

        self._container = QWidget()
        self._container_layout = QVBoxLayout()
        self._container_layout.setSpacing(4)
        self._container_layout.setContentsMargins(4, 6, 4, 6)
        self._container_layout.setAlignment(Qt.AlignTop)
        self._container.setLayout(self._container_layout)

        self._scroll_area.setWidget(self._container)
        self._scroll_area.installEventFilter(self)
        self._container.installEventFilter(self)
        super(ToolBar, self).addWidget(self._scroll_area)

    def setToolButtonStyle(self, style):
        self._tool_button_style = style
        super(ToolBar, self).setToolButtonStyle(style)
        for button in self._buttons:
            button.setToolButtonStyle(style)

    def toolButtonStyle(self):
        return self._tool_button_style

    def setIconSize(self, size):
        super(ToolBar, self).setIconSize(size)
        for button in self._buttons:
            button.setIconSize(size)

    def clear(self):
        self._buttons = []
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                if isinstance(widget, ToolButton) or isinstance(widget, QFrame):
                    widget.deleteLater()
                else:
                    widget.setParent(None)

    def addAction(self, action):
        if isinstance(action, QWidgetAction):
            widget = action.defaultWidget()
            if widget is not None:
                widget.setMinimumWidth(self._item_width)
                widget.setMaximumWidth(self._item_width)
                widget.installEventFilter(self)
                self._container_layout.addWidget(widget)
            return action
        btn = ToolButton()
        btn.setDefaultAction(action)
        btn.setObjectName('toolBarButton')
        btn.setToolButtonStyle(self.toolButtonStyle())
        btn.setIconSize(QSize(22, 22))
        btn.setMinimumWidth(self._item_width)
        btn.setMaximumWidth(self._item_width)
        btn.installEventFilter(self)
        self._buttons.append(btn)
        self._container_layout.addWidget(btn)
        return action

    def addSeparator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setObjectName('toolBarSeparator')
        sep.setMinimumWidth(self._item_width)
        sep.setMaximumWidth(self._item_width)
        sep.installEventFilter(self)
        self._container_layout.addWidget(sep)
        return sep

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Wheel:
            self._handle_wheel_scroll(event)
            return True
        return super(ToolBar, self).eventFilter(watched, event)

    def _handle_wheel_scroll(self, event):
        delta = 0
        if hasattr(event, 'angleDelta'):
            angle_delta = event.angleDelta()
            if angle_delta is not None:
                delta = angle_delta.y()
        if delta == 0 and hasattr(event, 'delta'):
            delta = event.delta()

        steps = int(delta / 120)
        if steps == 0:
            if delta > 0:
                steps = 1
            elif delta < 0:
                steps = -1
            else:
                return

        self._v_scrollbar.setValue(
            self._v_scrollbar.value() - (steps * self._v_scrollbar.singleStep())
        )


class ToolButton(QToolButton):
    """ToolBar companion class which ensures all buttons have the same size."""
    minSize = (96, 68)

    def minimumSizeHint(self):
        ms = super(ToolButton, self).minimumSizeHint()
        w1, h1 = ms.width(), ms.height()
        w2, h2 = self.minSize
        ToolButton.minSize = max(w1, w2), max(h1, h2)
        return QSize(*ToolButton.minSize)
