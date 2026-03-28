"""Modern, animated theme stylesheet for Labellix Studio.

Enhanced with:
- Smooth animations and transitions
- Beautiful hover effects
- Icon integration
- Improved visual hierarchy
- User-friendly design
"""

def _build_modern_theme(bg, bg2, bg3, fg, fg2, acc, acc2, acc3, border, sel_bg, sel_fg, tip_bg):
    """Build a complete, animated QSS stylesheet with modern effects."""
    return f"""
    /* ===== GLOBAL STYLES ===== */
    * {{
        font-family: "Segoe UI", "Ubuntu", "Noto Sans", sans-serif;
        font-size: 13px;
        outline: none;
    }}
    
    QMainWindow, QDialog {{ 
        background-color: {bg}; 
    }}
    
    QWidget {{ 
        background-color: {bg}; 
        color: {fg};
        selection-background-color: {acc}; 
        selection-color: {sel_fg}; 
    }}

    /* ===== CUSTOM TITLE BAR ===== */
    #titleBar {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                       stop:0 {bg2}, stop:0.5 {bg3}, stop:1 {bg2});
        border-bottom: 2px solid {acc};
        padding: 0px;
    }}
    
    #titleBarLabel {{
        background: transparent;
    }}
    
    #titleBarButton {{
        background: rgba(0, 194, 255, 15);
        color: {fg};
        border: 1px solid rgba(0, 194, 255, 30);
        border-radius: 4px;
        font-size: 16px;
        font-weight: bold;
        padding: 0px;
        margin: 0px 2px;
    }}
    
    #titleBarButton:hover {{
        background: rgba(0, 194, 255, 40);
        border: 1px solid {acc};
        color: {acc};
    }}
    
    #titleBarButton:pressed {{
        background: rgba(0, 194, 255, 60);
        border: 2px solid {acc};
    }}
    
    #titleBarCloseButton {{
        background: rgba(255, 100, 100, 15);
        color: #ff6464;
        border: 1px solid rgba(255, 100, 100, 30);
        border-radius: 4px;
        font-size: 16px;
        font-weight: bold;
        padding: 0px;
        margin: 0px 2px;
    }}
    
    #titleBarCloseButton:hover {{
        background: rgba(255, 100, 100, 50);
        border: 1px solid #ff6464;
        color: #ffffff;
    }}
    
    #titleBarCloseButton:pressed {{
        background: rgba(255, 100, 100, 80);
        border: 2px solid #ff6464;
    }}

    /* ===== MENU BAR ===== */
    QMenuBar {{ 
        background-color: {bg2}; 
        color: {fg};
        border-bottom: 2px solid {border}; 
        padding: 5px 8px; 
        spacing: 3px;
        margin: 0px;
    }}
    
    QMenuBar::item {{ 
        color: {fg}; 
        padding: 8px 16px; 
        border-radius: 8px; 
        background: transparent;
        margin: 2px 2px;
    }}
    
    QMenuBar::item:selected {{ 
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {sel_bg}, stop:1 {bg3});
        color: {acc3}; 
        border: 1px solid {acc2};
        border-radius: 8px;
    }}
    
    QMenuBar::item:pressed  {{ 
        background: {bg3}; 
        border: 1px solid {acc};
    }}

    /* ===== MENUS (Dropdown) ===== */
    QMenu {{ 
        background-color: {bg2}; 
        color: {fg}; 
        border: 1px solid {border};
        border-radius: 10px; 
        padding: 8px 4px;
        margin: 2px;
    }}
    
    QMenu::item {{ 
        padding: 10px 26px 10px 18px; 
        border-radius: 6px; 
        background: transparent;
        margin: 2px 6px;
    }}
    
    QMenu::item:selected {{ 
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {acc}, stop:1 {acc2});
        color: {sel_fg}; 
        border-radius: 6px;
        border: 1px solid {acc3};
    }}
    
    QMenu::item:pressed {{ 
        background: {acc3}; 
        color: {sel_fg};
    }}
    
    QMenu::separator {{ 
        height: 1px; 
        background: {border}; 
        margin: 6px 10px; 
    }}

    /* ===== TOOLBAR ===== */
    QToolBar {{ 
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                       stop:0 {bg2}, stop:1 {bg});
        border-right: 2px solid {border}; 
        spacing: 5px; 
        padding: 12px 6px;
        margin: 0px;
    }}
    
    QToolBar::separator {{ 
        background: {border}; 
        width: 2px; 
        height: 20px;
        margin: 4px 8px;
        border-radius: 1px;
    }}

    /* ===== TOOLBUTTON (with smooth transitions) ===== */
    QToolButton {{ 
        color: {fg2}; 
        background: rgba(255, 255, 255, 0.04); 
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px; 
        padding: 8px 10px; 
        min-width: 40px;
        min-height: 32px;
        margin: 2px;
    }}
    
    QToolButton:hover   {{ 
        color: {acc3}; 
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
            stop:0 rgba(255,255,255,0.08), stop:1 {sel_bg}); 
        border: 1px solid {acc};
        border-radius: 10px;
    }}
    
    QToolButton:pressed {{ 
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
            stop:0 {bg3}, stop:1 {bg2}); 
        color: {acc3}; 
        border: 1px solid {acc};
    }}
    
    QToolButton:checked {{ 
        color: {sel_fg};
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
            stop:0 {acc}, stop:1 {acc2});
        border: 2px solid {acc3};
        border-radius: 10px;
    }}
    
    QToolButton:disabled {{ 
        color: {border}; 
        background: transparent; 
        border: 1px solid transparent; 
    }}

    #customToolBar {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 {bg2}, stop:1 {bg});
        border-right: 1px solid {border};
    }}

    #toolBarButton {{
        min-height: 52px;
        min-width: 104px;
        padding: 8px 8px;
    }}

    #toolBarButton:hover {{
        border: 1px solid {acc};
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
            stop:0 {sel_bg}, stop:1 {bg2});
    }}

    #toolBarSeparator {{
        background: {border};
        max-height: 1px;
        margin: 6px 0;
    }}

    /* ===== DOCKWIDGET ===== */
    QDockWidget {{ 
        color: {fg}; 
        font-weight: 600;
        padding-top: 4px;
    }}
    
    QDockWidget::title {{
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
            stop:0 {sel_bg}, stop:1 {bg3});
        border: 1px solid {border}; 
        border-left: 3px solid {acc3};
        border-bottom: 2px solid {acc};
        padding: 10px 14px; 
        text-align: left;
        border-top-left-radius: 8px; 
        border-top-right-radius: 8px; 
        color: {acc3};
        font-weight: 700;
    }}
    
    QDockWidget::title:hover {{
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
            stop:0 {sel_bg}, stop:1 {acc2});
        border-left: 3px solid {acc};
    }}
    
    QDockWidget::close-button, QDockWidget::float-button {{
        background: transparent; 
        border: none; 
        padding: 0px; 
        margin: 0px 4px;
    }}
    
    QDockWidget::close-button:hover, QDockWidget::float-button:hover {{
        background: {bg3}; 
        border-radius: 5px; 
        border: 1px solid {acc};
    }}

    QDockWidget#labelsDock::title,
    QDockWidget#filesDock::title,
    QDockWidget#trainingLogs::title {{
        font-size: 12px;
        letter-spacing: 0.3px;
    }}

    /* ===== LISTWIDGET ===== */
    QListWidget {{ 
        background: {bg2}; 
        color: {fg}; 
        border: 1px solid {border};
        border-radius: 8px; 
        padding: 6px; 
        outline: none;
        alternate-background-color: {bg};
        spacing: 2px;
    }}
    
    QListWidget::item {{ 
        padding: 8px 12px; 
        border-radius: 6px; 
        border: none;
        margin: 2px 0px;
    }}
    
    QListWidget::item:selected {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 {acc}, stop:1 {acc2});
        color: {sel_fg}; 
        border-radius: 6px;
        border: 1px solid {acc3};
        padding-left: 14px;
        font-weight: 600;
    }}

    QListWidget::item:selected:active {{
        border: 2px solid {acc3};
    }}
    
    QListWidget::item:hover:!selected {{ 
        background: {sel_bg}; 
        color: {acc};
        border-radius: 6px;
        border: 1px solid {acc2};
    }}

    /* ===== COMBOBOX ===== */
    QComboBox {{ 
        background: {bg2}; 
        color: {fg}; 
        border: 1px solid {border};
        border-radius: 8px; 
        padding: 6px 12px 6px 14px; 
        min-height: 32px;
        margin: 2px;
    }}
    
    QComboBox:hover {{ 
        border: 1px solid {acc}; 
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {sel_bg}, stop:1 {bg2});
    }}
    
    QComboBox:focus {{ 
        border: 2px solid {acc3};
        background: {bg2};
    }}
    
    QComboBox::drop-down {{ 
        subcontrol-origin: padding; 
        subcontrol-position: center right;
        width: 30px; 
        border-left: 1px solid {border};
        border-top-right-radius: 8px; 
        border-bottom-right-radius: 8px;
        background: {bg3};
        margin-right: 2px;
    }}
    
    QComboBox::drop-down:hover {{
        background: {sel_bg};
    }}
    
    QComboBox::down-arrow {{ 
        width: 0; 
        height: 0;
        border-left: 5px solid transparent; 
        border-right: 5px solid transparent;
        border-top: 6px solid {acc}; 
        margin-right: 4px;
    }}
    
    QComboBox QAbstractItemView {{ 
        background: {bg2}; 
        color: {fg}; 
        border: 1px solid {border};
        border-radius: 6px; 
        selection-background-color: {acc}; 
        selection-color: {sel_fg};
        padding: 4px; 
        outline: none;
        spacing: 2px;
    }}
    
    QComboBox QAbstractItemView::item {{
        padding: 8px 12px;
        border-radius: 4px;
        margin: 2px 4px;
    }}
    
    QComboBox QAbstractItemView::item:hover {{
        background: {sel_bg};
        border: 1px solid {acc2};
    }}
    
    QComboBox QAbstractItemView::item:selected {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {acc}, stop:1 {acc2});
        color: {sel_fg};
        border: 1px solid {acc3};
    }}

    #comboContainer, #defaultLabelContainer {{
        background: transparent;
    }}

    #comboIcon, #defaultLabelIcon {{
        background: transparent;
        color: {fg2};
        padding-left: 4px;
        padding-right: 2px;
    }}

    QComboBox#labelFilterCombo,
    QComboBox#defaultLabelCombo {{
        min-height: 32px;
        border-radius: 8px;
        padding-left: 10px;
    }}

    /* ===== SPINBOX ===== */
    QSpinBox {{ 
        background: {bg2}; 
        color: {fg}; 
        border: 1px solid {border};
        border-radius: 8px; 
        padding: 6px 10px; 
        min-height: 32px;
        margin: 2px;
    }}
    
    QSpinBox:hover {{ 
        border: 1px solid {acc}; 
        background: {sel_bg};
    }}
    
    QSpinBox:focus {{ 
        border: 2px solid {acc3}; 
    }}
    
    QSpinBox::up-button, QSpinBox::down-button {{ 
        background: {bg3}; 
        border: none; 
        width: 20px;
        border-radius: 4px;
        margin: 1px;
    }}
    
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ 
        background: {sel_bg};
        border: 1px solid {acc};
    }}
    
    QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {{
        background: {acc};
    }}
    
    QSpinBox::up-arrow   {{ 
        width: 0; 
        height: 0; 
        border-left: 4px solid transparent;
        border-right: 4px solid transparent; 
        border-bottom: 5px solid {acc}; 
    }}
    
    QSpinBox::down-arrow {{ 
        width: 0; 
        height: 0; 
        border-left: 4px solid transparent;
        border-right: 4px solid transparent; 
        border-top: 5px solid {acc}; 
    }}

    /* ===== CHECKBOX ===== */
    QCheckBox {{ 
        color: {fg}; 
        spacing: 10px;
        padding: 4px;
    }}
    
    QCheckBox:hover {{ 
        color: {acc}; 
    }}
    
    QCheckBox::indicator {{ 
        width: 18px; 
        height: 18px; 
        border: 2px solid {border};
        border-radius: 5px; 
        background: {bg2};
        margin-right: 4px;
    }}
    
    QCheckBox::indicator:hover   {{ 
        border: 2px solid {acc}; 
        background: {sel_bg};
    }}
    
    QCheckBox::indicator:checked {{ 
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {acc}, stop:1 {acc2});
        border: 2px solid {acc3};
    }}
    
    QCheckBox::indicator:checked:hover {{
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {acc2}, stop:1 {acc});
    }}

    /* ===== PUSHBUTTON ===== */
    QPushButton {{ 
        color: {sel_fg};
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
            stop:0 {acc}, stop:1 {acc2});
        border: 1px solid {acc3}; 
        border-radius: 8px; 
        padding: 8px 18px;
        min-height: 32px; 
        font-weight: 600;
        margin: 2px;
    }}
    
    QPushButton:hover {{
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
            stop:0 {acc2}, stop:1 {acc});
        border: 2px solid {acc}; 
        padding: 7px 17px;
    }}
    
    QPushButton:pressed {{ 
        background: {acc3}; 
        border: 1px solid {acc2};
        padding: 9px 18px;
    }}
    
    QPushButton:disabled {{ 
        color: {border}; 
        background: {bg3}; 
        border: 1px solid {border}; 
    }}

    /* ===== STATUSBAR ===== */
    QStatusBar {{ 
        background: {bg2}; 
        color: {fg2}; 
        border-top: 2px solid {border}; 
        padding: 3px 10px; 
    }}
    
    QStatusBar::item {{ 
        border: none; 
    }}

    QStatusBar QToolButton#modeChip,
    QStatusBar QToolButton#formatChip,
    QStatusBar QToolButton#autosaveChip,
    QStatusBar QToolButton#counterChip {{
        padding: 2px 10px;
        border-radius: 10px;
        font-size: 11px;
        font-weight: 600;
    }}

    QPushButton#trainingPrimaryButton {{
        min-width: 122px;
        padding-top: 8px;
        padding-bottom: 10px;
    }}

    QPushButton#trainingPrimaryButton:hover {{
        border: 2px solid {acc};
        padding-top: 7px;
        padding-bottom: 11px;
    }}

    QPushButton#trainingPrimaryButton:pressed {{
        border: 1px solid {acc2};
        padding-top: 9px;
        padding-bottom: 9px;
    }}

    QPushButton#trainingSecondaryButton {{
        min-width: 122px;
        background: {bg3};
        color: {fg};
        border: 1px solid {border};
        padding-top: 8px;
        padding-bottom: 10px;
    }}

    QPushButton#trainingSecondaryButton:hover {{
        border: 2px solid {acc};
        background: {sel_bg};
        padding-top: 7px;
        padding-bottom: 11px;
    }}

    QPushButton#trainingSecondaryButton:pressed {{
        border: 1px solid {acc2};
        padding-top: 9px;
        padding-bottom: 9px;
    }}

    QPushButton#browseBtn:hover {{
        border: 2px solid {acc};
        padding-top: 7px;
        padding-bottom: 9px;
    }}

    QPushButton#browseBtn:pressed {{
        border: 1px solid {acc2};
        padding-top: 9px;
        padding-bottom: 7px;
    }}

    /* ===== SCROLLAREA ===== */
    QScrollArea {{ 
        border: 1px solid {border}; 
        background: {bg}; 
        border-radius: 6px;
        padding: 2px;
    }}

    /* ===== SCROLLBARS ===== */
    QScrollBar:vertical {{ 
        background: {bg}; 
        width: 12px; 
        margin: 0; 
        border-radius: 6px;
    }}
    
    QScrollBar::handle:vertical {{ 
        background: {acc2}; 
        min-height: 30px; 
        border-radius: 6px;
        margin: 3px 2px;
    }}
    
    QScrollBar::handle:vertical:hover   {{ 
        background: {acc};
    }}
    
    QScrollBar::handle:vertical:pressed {{ 
        background: {acc3}; 
    }}
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ 
        height: 0; 
        background: none; 
    }}
    
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ 
        background: transparent; 
    }}
    
    QScrollBar:horizontal {{ 
        background: {bg}; 
        height: 12px; 
        margin: 0; 
        border-radius: 6px;
    }}
    
    QScrollBar::handle:horizontal {{ 
        background: {acc2}; 
        min-width: 30px; 
        border-radius: 6px;
        margin: 2px 3px;
    }}
    
    QScrollBar::handle:horizontal:hover   {{ 
        background: {acc}; 
    }}
    
    QScrollBar::handle:horizontal:pressed {{ 
        background: {acc3}; 
    }}
    
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ 
        width: 0; 
        background: none; 
    }}
    
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ 
        background: transparent; 
    }}

    /* ===== TOOLTIP ===== */
    QToolTip {{ 
        color: {sel_fg}; 
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
            stop:0 {tip_bg}, stop:1 {bg3}); 
        border: 1px solid {acc3};
        border-radius: 10px; 
        padding:2px 5px;
        font-weight: 600;
        letter-spacing: 0.2px;
    }}

    /* ===== SPLITTER ===== */
    QSplitter::handle       {{ 
        background: {border}; 
        height: 2px;
    }}
    
    QSplitter::handle:hover {{ 
        background: {acc}; 
    }}

    /* ===== LINEEDIT ===== */
    QLineEdit {{ 
        background: {bg2}; 
        color: {fg}; 
        border: 1px solid {border};
        border-radius: 8px; 
        padding: 6px 12px; 
        min-height: 32px;
        margin: 2px;
        selection-background-color: {acc};
        selection-color: {sel_fg};
    }}
    
    QLineEdit:focus {{ 
        border: 2px solid {acc3};
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {sel_bg}, stop:1 {bg2});
    }}
    
    QLineEdit:hover {{ 
        border: 1px solid {acc}; 
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {sel_bg}, stop:1 {bg2});
    }}

    QDialog#labelDialog {{
        border: 1px solid {border};
        border-radius: 10px;
        background: {bg2};
    }}

    QLineEdit#labelInput {{
        font-size: 14px;
        min-height: 34px;
    }}

    QListWidget#labelDialogList {{
        min-height: 180px;
    }}

    QPushButton#restoreDefaultBtn {{
        min-width: 130px;
    }}

    QSpinBox#zoomWidget,
    QSpinBox#lightWidget {{
        min-width: 82px;
        font-weight: 600;
    }}

    /* ===== SLIDER ===== */
    QSlider::groove:horizontal {{ 
        background: {border}; 
        height: 5px; 
        border-radius: 3px;
        margin: 2px 0;
    }}
    
    QSlider::handle:horizontal {{ 
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {acc}, stop:1 {acc2});
        width: 16px; 
        height: 16px;
        margin: -6px 0; 
        border-radius: 8px; 
        border: 2px solid {acc3};
    }}
    
    QSlider::handle:horizontal:hover {{
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {acc2}, stop:1 {acc});
    }}
    
    QSlider::sub-page:horizontal {{ 
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {acc}, stop:1 {acc2});
        border-radius: 3px; 
    }}
    
    QSlider::groove:vertical {{ 
        background: {border}; 
        width: 5px; 
        border-radius: 3px;
        margin: 0 2px;
    }}
    
    QSlider::handle:vertical {{ 
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {acc}, stop:1 {acc2});
        width: 16px; 
        height: 16px;
        margin: 0 -6px; 
        border-radius: 8px; 
        border: 2px solid {acc3};
    }}
    
    QSlider::handle:vertical:hover {{
        background: qlineargradient(x1:1,y1:0,x2:0,y2:0, stop:0 {acc2}, stop:1 {acc});
    }}
    
    QSlider::sub-page:vertical {{ 
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {acc}, stop:1 {acc2});
        border-radius: 3px; 
    }}

    /* ===== TABBAR ===== */
    QTabBar::tab {{ 
        background: {bg3}; 
        color: {fg2}; 
        border: 1px solid {border};
        border-bottom: none; 
        border-top-left-radius: 8px; 
        border-top-right-radius: 8px;
        padding: 8px 18px; 
        min-width: 90px;
        margin-right: 2px;
    }}
    
    QTabBar::tab:selected {{ 
        background: {bg2}; 
        color: {acc3};
        border-bottom: 3px solid {acc}; 
        font-weight: 600;
    }}
    
    QTabBar::tab:hover:!selected {{ 
        background: {sel_bg}; 
        color: {acc};
        border-bottom: 1px solid {acc2};
    }}
    
    QTabWidget::pane {{ 
        border: 1px solid {border}; 
        background: {bg2};
        border-radius: 0 8px 8px 8px;
    }}
    """

# Color Palettes
PALETTES = {
    "futuristic": {
        "bg": "#11161d",
        "bg2": "#17212c",
        "bg3": "#223141",
        "fg": "#e7edf5",
        "fg2": "#a8b6c7",
        "acc": "#4ca3dd",
        "acc2": "#3d8fc5",
        "acc3": "#8ec8ed",
        "border": "#32485f",
        "sel_bg": "#263b52",
        "sel_fg": "#ffffff",
        "tip_bg": "#1b2a3a",
    },
    "light": {
        "bg": "#f5f7fa",
        "bg2": "#ffffff",
        "bg3": "#e8eef5",
        "fg": "#2c3e50",
        "fg2": "#34495e",
        "acc": "#3498db",
        "acc2": "#2980b9",
        "acc3": "#1d5aa0",
        "border": "#bdc3c7",
        "sel_bg": "#d6eaf8",
        "sel_fg": "#ffffff",
        "tip_bg": "#2c3e50",
    },
    "yellow": {
        "bg": "#fffbf0",
        "bg2": "#fff8e1",
        "bg3": "#ffe0b2",
        "fg": "#3e2800",
        "fg2": "#5a4000",
        "acc": "#f39c12",
        "acc2": "#e67e22",
        "acc3": "#d35400",
        "border": "#f0c040",
        "sel_bg": "#ffeaa7",
        "sel_fg": "#ffffff",
        "tip_bg": "#3e2800",
    },
    "dark": {
        "bg": "#1a1a2e",
        "bg2": "#16213e",
        "bg3": "#1f3b6d",
        "fg": "#f2f6ff",
        "fg2": "#d6def4",
        "acc": "#5cc8ff",
        "acc2": "#2a9fd6",
        "acc3": "#9fe6ff",
        "border": "#5a698a",
        "sel_bg": "#294b7a",
        "sel_fg": "#ffffff",
        "tip_bg": "#162947",
    },
}

def _build_theme(name="light"):
    """Build theme stylesheet from palette."""
    palette = PALETTES.get(name, PALETTES["light"])
    return _build_modern_theme(**palette)

# Theme exports
FUTURISTIC_THEME = _build_theme("futuristic")
LIGHT_THEME = _build_theme("light")
YELLOW_THEME = _build_theme("yellow")
DARK_THEME = _build_theme("dark")

THEMES = {
    "futuristic": FUTURISTIC_THEME,
    "light": LIGHT_THEME,
    "yellow": YELLOW_THEME,
    "dark": DARK_THEME,
}
