from libs.utils import add_actions


class ModeWorkflowsMixin(object):
    """Mode toggles and draw-mode interaction workflow helpers."""

    def create_shape(self):
        assert self.beginner()
        self.canvas.set_editing(False)
        self.actions.create.setEnabled(False)

    def toggle_drawing_sensitive(self, drawing=True):
        """In the middle of drawing, toggling between modes should be disabled."""
        self.actions.editMode.setEnabled(not drawing)
        if not drawing and self.beginner():
            print('Cancel creation.')
            self.canvas.set_editing(True)
            self.canvas.restore_cursor()
            self.actions.create.setEnabled(True)

    def toggle_draw_mode(self, edit=True):
        self.canvas.set_editing(edit)
        self.actions.createMode.setEnabled(edit)
        self.actions.drawPolygon.setEnabled(edit)
        self.actions.editMode.setEnabled(not edit)

    def set_create_mode(self):
        self.toggle_draw_mode(False)

    def set_edit_mode(self):
        self.toggle_draw_mode(True)
        self.label_selection_changed()

    def draw_polygon(self):
        """Enable polygon drawing mode (P key)."""
        self.canvas.set_segmentation_mode(True)
        self.toggle_draw_mode(False)

    def toggle_advanced_mode(self, value=True):
        if self.is_classification_mode():
            return
        self._beginner = not value
        self.canvas.set_editing(True)
        self.populate_mode_actions()
        self.edit_button.setVisible(not value)
        if value:
            self.actions.createMode.setEnabled(True)
            self.actions.drawPolygon.setEnabled(True)
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
