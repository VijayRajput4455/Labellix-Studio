import os
import shutil

try:
    from PyQt5.QtWidgets import QMessageBox, QInputDialog
except ImportError:
    from PyQt4.QtGui import QMessageBox, QInputDialog

from libs.classification_io import ClassificationIOError
from libs.constants import (
    SETTING_CLASSIFICATION_DATASET_NAME,
    SETTING_CLASSIFICATION_EXPORT_DIR,
    SETTING_CLASSIFICATION_EXPORT_MOVE,
    SETTING_CLASSIFICATION_EXPORT_ZIP,
    SETTING_LICENSE_PLATE_DATASET_NAME,
    SETTING_LICENSE_PLATE_EXPORT_DIR,
    SETTING_LICENSE_PLATE_EXPORT_IMAGE_MODE,
    SETTING_LICENSE_PLATE_EXPORT_MOVE,
    SETTING_LICENSE_PLATE_EXPORT_ZIP,
    SETTING_YOLO_EXPORT_DIR,
    SETTING_YOLO_LAST_DATASET_YAML,
)
from libs.license_plate_export_dialog import LicensePlateExportConfigDialog
from libs.license_plate_io import LicensePlateDatasetSession, LicensePlateIOError
from libs.ustr import ustr
from libs.utils import trimmed
from libs.yolo_export_dialog import YOLOExportConfigDialog
from libs.yolo_io import TXT_EXT, YOLODatasetSession, YOLODatasetExportError


class ExportWorkflowsMixin(object):
    """Encapsulates dataset export flows to keep MainWindow focused on UI orchestration."""

    def export_classification_dataset(self, _value=False):
        if not self.is_classification_mode() or not self.m_img_list:
            return

        unlabeled = [image_path for image_path in self.m_img_list if not self.classification_labels.get(image_path)]
        if unlabeled:
            self.error_message(self.get_str('classificationExportError'), self.get_str('classificationExportBlocked'))
            return

        source_dir = self.classification_source_dir()
        default_dir = self.classification_export_dir or source_dir or '.'
        strings = {
            'browse': self.get_str('browse', 'Browse'),
            'exportDir': self.get_str('exportDir', 'Export folder'),
            'datasetName': self.get_str('datasetFolderName', 'Dataset folder name'),
            'transferMode': self.get_str('transferMode', 'Transfer mode'),
            'copyMode': self.get_str('copyMode', 'Copy'),
            'moveMode': self.get_str('moveMode', 'Move'),
            'zip': self.get_str('createZipAfterExport', 'Create zip after export'),
            'chooseExportDirTitle': self.get_str('chooseExportDirTitle', 'Choose export folder'),
            'missingExportDir': self.get_str('missingExportDir', 'Please choose an export folder.'),
            'invalidExportDir': self.get_str('invalidExportDir', 'Export folder does not exist.'),
            'missingDatasetName': self.get_str('missingDatasetName', 'Please enter dataset folder name.'),
        }
        dialog = LicensePlateExportConfigDialog(
            self,
            title=self.get_str('exportClasses', 'Export Classification Dataset'),
            defaults={
                'export_dir': default_dir,
                'dataset_name': self.classification_dataset_name or 'dataset',
                'transfer_mode': 'move' if self.classification_export_move_images else 'copy',
                'create_zip': self.classification_export_create_zip,
            },
            strings=strings,
        )
        config = dialog.get_config()
        if not config:
            return

        export_dir = config.get('export_dir', '')
        dataset_name = config.get('dataset_name', '')
        move_images = bool(config.get('move_images', False))
        create_zip = bool(config.get('create_zip', False))

        self.classification_export_move_images = move_images
        self.classification_export_create_zip = create_zip
        self.classification_dataset_name = dataset_name
        self.settings[SETTING_CLASSIFICATION_EXPORT_MOVE] = move_images
        self.settings[SETTING_CLASSIFICATION_EXPORT_ZIP] = create_zip
        self.settings[SETTING_CLASSIFICATION_DATASET_NAME] = dataset_name

        dataset_root = os.path.join(export_dir, dataset_name)
        session = self.classification_service.build_export_session(
            source_dir=source_dir,
            label_hist=self.label_hist,
            classification_labels=self.classification_labels,
        )
        try:
            session.export_dataset(dataset_root, move_images=move_images)
        except ClassificationIOError as e:
            self.error_message(self.get_str('classificationExportError'), u'<b>%s</b>' % e)
            return

        if create_zip:
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
        strings = {
            'browse': self.get_str('browse', 'Browse'),
            'exportDir': self.get_str('exportDir', 'Export folder'),
            'datasetName': self.get_str('datasetFolderName', 'Dataset folder name'),
            'transferMode': self.get_str('licensePlateTransferModeLabel', 'Transfer mode'),
            'imageMode': self.get_str('licensePlateImageModeLabel', 'Image export mode'),
            'imageModeCropped': self.get_str('licensePlateImageModeCropped', 'Cropped plates only'),
            'imageModeFull': self.get_str('licensePlateImageModeFull', 'Full image + labels'),
            'copyMode': self.get_str('copyMode', 'Copy'),
            'moveMode': self.get_str('moveMode', 'Move'),
            'zip': self.get_str('createZipAfterExport', 'Create zip after export'),
            'chooseExportDirTitle': self.get_str('chooseExportDirTitle', 'Choose export folder'),
            'missingExportDir': self.get_str('missingExportDir', 'Please choose an export folder.'),
            'invalidExportDir': self.get_str('invalidExportDir', 'Export folder does not exist.'),
            'missingDatasetName': self.get_str('missingDatasetName', 'Please enter dataset folder name.'),
        }
        dialog = LicensePlateExportConfigDialog(
            self,
            title=self.get_str('exportLicensePlateDataset', 'Export License Plate Dataset'),
            defaults={
                'export_dir': default_dir,
                'dataset_name': self.license_plate_dataset_name or 'license_plate_dataset',
                'transfer_mode': 'move' if self.license_plate_export_move_images else 'copy',
                'create_zip': self.license_plate_export_create_zip,
                'show_image_mode': True,
                'image_mode': self.license_plate_export_image_mode or 'full',
            },
            strings=strings,
        )
        config = dialog.get_config()
        if not config:
            return

        export_dir = config.get('export_dir', '')
        dataset_name = config.get('dataset_name', '')
        move_images = bool(config.get('move_images', False))
        create_zip = bool(config.get('create_zip', False))
        image_mode = ustr(config.get('image_mode', 'full'))
        crop_plates_only = image_mode != 'full'

        self.license_plate_export_move_images = move_images
        self.license_plate_export_create_zip = create_zip
        self.license_plate_dataset_name = dataset_name
        self.license_plate_export_image_mode = image_mode
        self.settings[SETTING_LICENSE_PLATE_EXPORT_MOVE] = move_images
        self.settings[SETTING_LICENSE_PLATE_EXPORT_ZIP] = create_zip
        self.settings[SETTING_LICENSE_PLATE_DATASET_NAME] = dataset_name
        self.settings[SETTING_LICENSE_PLATE_EXPORT_IMAGE_MODE] = image_mode

        dataset_root = os.path.join(export_dir, dataset_name)
        session = LicensePlateDatasetSession(source_dir=source_dir)
        try:
            result = session.export_dataset(
                output_dir=dataset_root,
                image_paths=self.m_img_list,
                move_images=move_images,
                skip_unlabeled=True,
                crop_plates_only=crop_plates_only,
            )
        except LicensePlateIOError as e:
            self.error_message(self.get_str('licensePlateExportError', 'License plate export error'), u'<b>%s</b>' % e)
            return

        if create_zip:
            try:
                shutil.make_archive(dataset_root, 'zip', os.path.dirname(dataset_root), os.path.basename(dataset_root))
            except Exception as e:
                self.error_message(self.get_str('licensePlateExportError', 'License plate export error'), u'<b>%s</b>' % e)
                return

        self.license_plate_export_dir = export_dir
        self.settings[SETTING_LICENSE_PLATE_EXPORT_DIR] = export_dir
        self.status('%s (%d exported, %d skipped)' % (
            self.get_str('licensePlateExportDone', 'License plate dataset export completed.'),
            result.get('exported_count', 0),
            result.get('skipped_unlabeled', 0),
        ))

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
