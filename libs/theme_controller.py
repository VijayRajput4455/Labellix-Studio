#!/usr/bin/env python
# -*- coding: utf-8 -*-

from math import sin

try:
    from PyQt5.QtCore import QEasingCurve, QPropertyAnimation, QTimer, QSize
    from PyQt5.QtGui import QColor
    from PyQt5.QtWidgets import QAction, QApplication, QGraphicsOpacityEffect, QToolButton
except ImportError:
    from PyQt4.QtCore import QEasingCurve, QTimer, QSize, QPropertyAnimation
    from PyQt4.QtGui import QAction, QApplication, QColor, QGraphicsOpacityEffect, QToolButton

from libs.utils import set_icon_preferences


class ThemeController(object):
    THEME_ORDER = ('futuristic', 'light', 'yellow', 'dark')

    def __init__(self, window, themes, palettes, default_theme='light'):
        self.window = window
        self.themes = themes
        self.palettes = palettes
        self.default_theme = default_theme if default_theme in themes else 'light'
        self.current_theme = self.default_theme
        self._theme_actions = []

    def setup_theme_menu(self, menu):
        labels = {
            'futuristic': 'Slate Pro',
            'light': 'Light Blue',
            'yellow': 'Yellow / Warm',
            'dark': 'Dark',
        }

        actions = []
        for theme_name in self.THEME_ORDER:
            action = QAction(labels[theme_name], self.window, checkable=True)
            action.setChecked(theme_name == self.current_theme)
            action.triggered.connect(lambda _checked=False, name=theme_name: self.apply_theme(name))
            actions.append(action)
            menu.addAction(action)

        self._theme_actions = actions
        return actions

    def apply_theme(self, theme_name, action_list=None):
        self.current_theme = theme_name if theme_name in self.themes else self.default_theme
        self.apply_modern_ui()

        if action_list is None:
            action_list = self._theme_actions

        for index, action in enumerate(action_list):
            action.setChecked(index < len(self.THEME_ORDER) and self.THEME_ORDER[index] == self.current_theme)

    def motion_profile(self):
        if self.window.reduced_motion:
            return {
                'dock_fade_ms': 0,
                'panel_fade_ms': 0,
                'dialog_fade_ms': 0,
                'chip_step': 0.0,
                'chip_alpha_base': 0,
                'chip_alpha_range': 0,
                'chip_bright_base': 100,
                'chip_bright_range': 0,
                'chip_timer_ms': 0,
                'easing': QEasingCurve.Linear,
            }

        by_theme = {
            'futuristic': {'dock_fade_ms': 150, 'panel_fade_ms': 180, 'chip_step': 0.16, 'chip_timer_ms': 110, 'easing': QEasingCurve.OutCubic},
            'light': {'dock_fade_ms': 140, 'panel_fade_ms': 170, 'chip_step': 0.13, 'chip_timer_ms': 120, 'easing': QEasingCurve.OutQuad},
            'yellow': {'dock_fade_ms': 150, 'panel_fade_ms': 175, 'chip_step': 0.14, 'chip_timer_ms': 120, 'easing': QEasingCurve.OutQuad},
            'dark': {'dock_fade_ms': 165, 'panel_fade_ms': 185, 'chip_step': 0.18, 'chip_timer_ms': 105, 'easing': QEasingCurve.OutCubic},
        }
        profile = by_theme.get(self.current_theme, by_theme['light'])
        profile.update({
            'dialog_fade_ms': 150,
            'chip_alpha_base': 145,
            'chip_alpha_range': 70,
            'chip_bright_base': 101,
            'chip_bright_range': 12,
        })
        return profile

    def sync_motion_profile(self):
        profile = self.motion_profile()
        timer_ms = profile['chip_timer_ms']
        if timer_ms > 0:
            self.window._mode_glow_timer.setInterval(timer_ms)
            if not self.window._mode_glow_timer.isActive():
                self.window._mode_glow_timer.start()
        else:
            self.window._mode_glow_timer.stop()

    def apply_modern_ui(self):
        compact_mode = self.window.compact_mode_option.isChecked() if hasattr(self.window, 'compact_mode_option') else False
        stylesheet = self.themes.get(self.current_theme, self.themes[self.default_theme])
        palette = self.palettes.get(self.current_theme, self.palettes[self.default_theme])
        icon_tint = palette.get('acc3')
        set_icon_preferences(self.window.use_modern_icons, True, True, icon_tint)
        self.sync_motion_profile()
        if compact_mode:
            stylesheet += """
            QMenuBar::item { padding: 6px 10px; }
            QToolBar { spacing: 3px; padding: 6px 4px; }
            QToolButton { padding: 5px 4px; min-width: 32px; min-height: 24px; }
            QListWidget::item { padding: 5px 8px; }
            QComboBox, QLineEdit, QSpinBox, QPushButton { min-height: 24px; padding: 4px 8px; }
            QDockWidget::title { padding: 8px 10px; }
            """
        QApplication.instance().setStyleSheet(stylesheet)
        self.window.label_list.setAlternatingRowColors(True)
        self.window.file_list_widget.setAlternatingRowColors(True)
        self.window.label_list.setSpacing(1 if compact_mode else 2)
        self.window.file_list_widget.setSpacing(1 if compact_mode else 2)
        self.window.tools.setIconSize(QSize(18, 18) if compact_mode else QSize(24, 24))
        self.window.refresh_ui_icons()
        if hasattr(self.window, 'training_config_panel'):
            self.window.training_config_panel._apply_panel_style()
        self.window.update_status_chips()

    def chip_palette(self):
        theme_name = self.current_theme
        if theme_name == 'dark':
            return {
                'neutral': ('#26334f', '#e8f1ff', '#46608a'),
                'mode_detection': ('#2b405f', '#dff2ff', '#4b7eb8'),
                'mode_segmentation': ('#2a315f', '#f3ecff', '#8b7de0'),
                'mode_classification': ('#214a3e', '#dfffea', '#39a87f'),
                'autosave_on': ('#1f4f3f', '#dfffea', '#35b083'),
                'autosave_off': ('#4d2f2f', '#ffe7e7', '#b56c6c'),
            }
        if theme_name == 'yellow':
            return {
                'neutral': ('#fff1cb', '#4a3200', '#e6b552'),
                'mode_detection': ('#ffe6a8', '#5a3b00', '#d79a2a'),
                'mode_segmentation': ('#efe4ff', '#4f2f8a', '#b198ef'),
                'mode_classification': ('#dff4e9', '#194a2f', '#47a36d'),
                'autosave_on': ('#dff4e9', '#194a2f', '#47a36d'),
                'autosave_off': ('#ffe3de', '#7a2a20', '#d27b6f'),
            }
        return {
            'neutral': ('#edf3ff', '#2a3f63', '#c7d9fb'),
            'mode_detection': ('#e9f2ff', '#204c7a', '#9cc0f3'),
            'mode_segmentation': ('#f2ecff', '#4f3f8f', '#baa6ef'),
            'mode_classification': ('#e7f9f0', '#1f5a43', '#8fdab6'),
            'autosave_on': ('#e7f9f0', '#1f5a43', '#8fdab6'),
            'autosave_off': ('#ffe9e6', '#7b2f25', '#f1a69d'),
        }

    @staticmethod
    def set_chip_style(label, bg, fg, border):
        selector = 'QToolButton' if isinstance(label, QToolButton) else 'QLabel'
        label.setStyleSheet(
            '%s {' % selector +
            ' padding: 2px 10px;'
            ' border-radius: 10px;'
            ' border: 1px solid %s;'
            ' background: %s;'
            ' color: %s;'
            ' font-weight: 600;'
            ' min-height: 18px;'
            '}' % (border, bg, fg)
        )

    def animate_mode_chip(self):
        if not hasattr(self.window, 'mode_status_label'):
            return

        palette = self.chip_palette()
        mode_key = self.window._current_mode_key()
        if mode_key not in palette:
            return

        bg, fg, border = palette[mode_key]
        if getattr(self.window, 'reduced_motion', False):
            self.window.mode_status_label.setStyleSheet(
                'QToolButton {'
                ' padding: 2px 10px;'
                ' border-radius: 10px;'
                ' border: 1px solid %s;'
                ' background: %s;'
                ' color: %s;'
                ' font-weight: 700;'
                ' min-height: 18px;'
                '}' % (border, bg, fg)
            )
            return

        profile = self.motion_profile()
        self.window._mode_glow_phase += profile.get('chip_step', 0.16)
        pulse = (sin(self.window._mode_glow_phase) + 1.0) / 2.0
        border_color = QColor(border)
        border_color.setAlpha(profile.get('chip_alpha_base', 145) + int(profile.get('chip_alpha_range', 70) * pulse))
        bg_color = QColor(bg)
        bright_bg = bg_color.lighter(profile.get('chip_bright_base', 101) + int(profile.get('chip_bright_range', 12) * pulse))
        self.window.mode_status_label.setStyleSheet(
            'QToolButton {'
            ' padding: 2px 10px;'
            ' border-radius: 10px;'
            ' border: 1px solid %s;'
            ' background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 %s, stop:1 %s);'
            ' color: %s;'
            ' font-weight: 700;'
            ' min-height: 18px;'
            '}' % (border_color.name(QColor.HexArgb), bright_bg.name(), bg_color.name(), fg)
        )
