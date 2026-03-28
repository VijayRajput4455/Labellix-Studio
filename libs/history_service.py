#!/usr/bin/env python
# -*- coding: utf-8 -*-

try:
    from PyQt5.QtCore import QTimer
except ImportError:
    from PyQt4.QtCore import QTimer


class HistoryService(object):
    """Manage annotation undo/redo stacks with checkpoint timer support."""

    def __init__(self, parent, max_entries=100, checkpoint_interval_ms=250):
        self.max_entries = int(max_entries)
        self.undo_stack = []
        self.redo_stack = []
        self.baseline_state = None
        self.restoring = False
        self.suppress_capture = False

        self.timer = QTimer(parent)
        self.timer.setInterval(int(checkpoint_interval_ms))
        self.timer.setSingleShot(True)

    def reset(self):
        self.timer.stop()
        self.undo_stack = []
        self.redo_stack = []
        self.baseline_state = None

    def initialize(self, state):
        self.reset()
        self.undo_stack.append(state)
        self.baseline_state = state

    def capture(self, state, clear_redo=True):
        if self.restoring or self.suppress_capture:
            return False

        if self.undo_stack and self.undo_stack[-1] == state:
            return False

        self.undo_stack.append(state)
        if len(self.undo_stack) > self.max_entries:
            self.undo_stack.pop(0)
        if clear_redo:
            self.redo_stack = []
        return True

    def can_undo(self):
        return len(self.undo_stack) > 1

    def can_redo(self):
        return len(self.redo_stack) > 0

    def pop_undo_target(self):
        if not self.can_undo():
            return None
        current_state = self.undo_stack.pop()
        self.redo_stack.append(current_state)
        return self.undo_stack[-1]

    def pop_redo_target(self):
        if not self.can_redo():
            return None
        target_state = self.redo_stack.pop()
        self.undo_stack.append(target_state)
        return target_state

    def is_at_baseline(self, state):
        return self.baseline_state is not None and state == self.baseline_state

    def start_restore(self):
        self.restoring = True

    def end_restore(self):
        self.restoring = False

    def request_checkpoint(self, enabled=True):
        if enabled and not self.restoring:
            self.timer.start()

    def set_suppress_capture(self, value):
        self.suppress_capture = bool(value)
