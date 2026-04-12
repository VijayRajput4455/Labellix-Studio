import os
import time

try:
    from PyQt5.QtCore import QUrl
    from PyQt5.QtGui import QDesktopServices
    from PyQt5.QtWidgets import QFileDialog, QMessageBox
except ImportError:
    from PyQt4.QtCore import QUrl
    from PyQt4.QtGui import QFileDialog, QMessageBox, QDesktopServices

from libs.training_runner import (
    format_command_for_display,
    infer_run_artifacts,
    parse_yolov8_progress_line,
)


class TrainingWorkflowsMixin(object):
    """Encapsulates training workflow UI/event logic outside MainWindow."""

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
        self.training_worker = self._new_training_worker(command)
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
