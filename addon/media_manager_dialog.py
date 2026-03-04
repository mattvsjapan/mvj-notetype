"""
Media Manager Dialog for MvJ note type addon.

Provides a UI for managing unused and duplicate media files across
source folder and Anki media folder. Adapted from MvJ Japanese's
media manager dialog for standalone use.
"""

import os
from typing import Optional

from aqt import mw
from aqt.operations import QueryOp
from aqt.qt import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    Qt,
    qconnect,
)
from aqt.utils import tooltip

from . import media_service as ms


def _show_dialog_centered_on_parent(
    parent,
    icon: QMessageBox.Icon,
    title: str,
    text: str,
    buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
    default_button: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
    informative_text: str = ""
) -> QMessageBox.StandardButton:
    """Show a QMessageBox centered on the parent window."""
    if not parent:
        parent = mw.app.activeWindow() or mw

    msg_box = QMessageBox(parent)
    msg_box.setIcon(icon)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    if informative_text:
        msg_box.setInformativeText(informative_text)
    msg_box.setStandardButtons(buttons)
    msg_box.setDefaultButton(default_button)
    msg_box.setWindowModality(Qt.WindowModality.WindowModal)

    msg_box.adjustSize()

    # CRITICAL for macOS: show() BEFORE move() prevents Qt auto-centering on exec()
    msg_box.show()

    parent.raise_()
    parent.activateWindow()
    QApplication.processEvents()

    try:
        parent_rect = parent.frameGeometry()
        msg_box_rect = msg_box.frameGeometry()

        center_x = parent_rect.x() + (parent_rect.width() - msg_box_rect.width()) // 2
        center_y = parent_rect.y() + (parent_rect.height() - msg_box_rect.height()) // 2

        msg_box.move(center_x, center_y)
    except Exception as e:
        ms._log(f"Failed to center message box: {e}")

    result = msg_box.exec()
    return QMessageBox.StandardButton(result)


class MediaManagerDialog(QDialog):
    """Dialog for managing unused and duplicate media files."""

    _instance_open = False

    def __init__(self, analysis_result: dict, source_folder=None, parent=None):
        if not parent:
            parent = mw

        super().__init__(parent)
        self._analysis_result = analysis_result
        self._source_folder = source_folder
        self._setup_ui()
        self._update_ui_with_results()

    def _setup_ui(self):
        self.setWindowTitle("Manage Media")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400 if self._source_folder else 250)

        layout = QVBoxLayout()
        self.setLayout(layout)

        title_label = QLabel("Media Usage Analysis")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)

        if self._source_folder:
            desc_text = (
                "This tool analyzes media files in your source folder and Anki media folder.\n"
                "You can safely delete unreferenced and duplicate files to save disk space."
            )
        else:
            desc_text = (
                "This tool analyzes media files in your Anki media folder.\n"
                "You can safely delete unreferenced files to save disk space."
            )
        desc_label = QLabel(desc_text)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("margin-bottom: 15px;")
        layout.addWidget(desc_label)

        # Source Folder Group
        source_group = QGroupBox("Source Media Folder")
        source_layout = QVBoxLayout()
        source_group.setLayout(source_layout)

        self._unreferenced_label = QLabel()
        self._duplicated_label = QLabel()
        self._used_label = QLabel()

        source_layout.addWidget(self._unreferenced_label)
        source_layout.addWidget(self._duplicated_label)
        source_layout.addWidget(self._used_label)

        layout.addWidget(source_group)

        # Hide source group when no source folder
        source_group.setVisible(self._source_folder is not None)

        # Anki Folder Group
        anki_group = QGroupBox("Anki Media Folder")
        anki_layout = QVBoxLayout()
        anki_group.setLayout(anki_layout)

        self._orphaned_label = QLabel()
        self._protected_label = QLabel()
        self._anki_used_label = QLabel()
        anki_layout.addWidget(self._orphaned_label)
        anki_layout.addWidget(self._protected_label)
        anki_layout.addWidget(self._anki_used_label)

        layout.addWidget(anki_group)

        layout.addStretch()

        # Action Buttons
        button_layout = QHBoxLayout()

        self._delete_unreferenced_btn = QPushButton("Delete Source Unused")
        self._delete_unreferenced_btn.setEnabled(False)
        qconnect(self._delete_unreferenced_btn.clicked, self._on_delete_unreferenced)

        self._delete_duplicated_btn = QPushButton("Delete Source Duplicates")
        self._delete_duplicated_btn.setEnabled(False)
        qconnect(self._delete_duplicated_btn.clicked, self._on_delete_duplicated)

        self._delete_orphaned_btn = QPushButton("Delete Anki Unused")
        self._delete_orphaned_btn.setEnabled(False)
        qconnect(self._delete_orphaned_btn.clicked, self._on_delete_orphaned)

        # Only show source delete buttons when source folder exists
        if self._source_folder:
            button_layout.addWidget(self._delete_unreferenced_btn)
            button_layout.addWidget(self._delete_duplicated_btn)
        button_layout.addWidget(self._delete_orphaned_btn)

        layout.addLayout(button_layout)

        # Dialog buttons (Close)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        qconnect(button_box.rejected, self.reject)
        layout.addWidget(button_box)

    def _refresh_analysis(self):
        """Re-run analysis and update UI (called after deletion)."""
        progress = QProgressDialog("Re-analyzing media files...", None, 0, 0, self)
        progress.setWindowTitle("Please Wait")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)
        progress.show()

        def on_success(result: dict):
            progress.close()
            self._analysis_result = result
            self._update_ui_with_results()
            ms._log("Re-analysis complete")

        def on_failure(error):
            progress.close()
            ms._log(f"Re-analysis failed: {error}")
            _show_dialog_centered_on_parent(
                self,
                QMessageBox.Icon.Critical,
                "Re-analysis Failed",
                f"Failed to re-analyze media files: {error}"
            )

        op = QueryOp(
            parent=self,
            op=lambda col: ms.analyze_media_usage(source_folder=self._source_folder),
            success=on_success
        )
        op.failure(on_failure)
        op.run_in_background()

    def _update_ui_with_results(self):
        if not self._analysis_result:
            return

        result = self._analysis_result

        unreferenced_count = len(result['source_unreferenced'])
        duplicated_count = len(result['source_duplicated'])
        used_count = len(result['source_used'])
        orphaned_count = len(result['anki_orphaned'])
        protected_count = len(result.get('anki_protected', []))
        anki_used_count = len(result.get('anki_used', []))

        self._unreferenced_label.setText(
            f"Unused files: {unreferenced_count} "
            f"(not used by any card)"
        )
        self._duplicated_label.setText(
            f"Duplicated files: {duplicated_count} "
            f"(used by cards, but also in Anki folder)"
        )
        self._used_label.setText(
            f"In-use files: {used_count} "
            f"(used by cards, only in source folder)"
        )
        self._orphaned_label.setText(
            f"Unused files: {orphaned_count} "
            f"(in Anki folder but not used by any card)"
        )
        self._protected_label.setText(
            f"Protected files: {protected_count} "
            f"(names start with underscore, preserved by Anki)"
        )
        self._anki_used_label.setText(
            f"In-use files: {anki_used_count} "
            f"(actively used by cards)"
        )

        self._delete_unreferenced_btn.setEnabled(unreferenced_count > 0)
        self._delete_duplicated_btn.setEnabled(duplicated_count > 0)
        self._delete_orphaned_btn.setEnabled(orphaned_count > 0)

    def _on_delete_unreferenced(self):
        if not self._analysis_result:
            return

        files = self._analysis_result['source_unreferenced']
        if not files:
            return

        self._delete_files_from_source(files)

    def _on_delete_duplicated(self):
        if not self._analysis_result:
            return

        files = self._analysis_result['source_duplicated']
        if not files:
            return

        self._delete_files_from_source(files)

    def _on_delete_orphaned(self):
        if not self._analysis_result:
            return

        files = self._analysis_result['anki_orphaned']
        if not files:
            return

        self._delete_files_from_anki(files)

    def _delete_files_from_source(self, files: list[str]):
        source_folder = self._source_folder
        if not source_folder:
            _show_dialog_centered_on_parent(
                self,
                QMessageBox.Icon.Critical,
                "Error",
                "Source folder not configured"
            )
            return

        total = len(files)
        progress = QProgressDialog("Deleting files from source folder...", None, 0, 100, self)
        progress.setWindowTitle("Deleting Files")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)
        progress.show()

        def do_delete(col):
            deleted_count = 0
            errors = []
            last_percent = -1

            for i, filename in enumerate(files):
                percent = (i * 100) // total
                if percent > last_percent:
                    mw.taskman.run_on_main(lambda p=percent: progress.setValue(p))
                    last_percent = percent

                file_path = os.path.join(source_folder, filename)
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        deleted_count += 1
                except Exception as e:
                    ms._log(f"Failed to delete {filename}: {e}")
                    errors.append(f"{filename}: {e}")

            return {"deleted_count": deleted_count, "errors": errors}

        def on_success(result: dict):
            progress.close()
            errors = result["errors"]
            deleted_count = result["deleted_count"]

            if errors:
                _show_dialog_centered_on_parent(
                    self,
                    QMessageBox.Icon.Warning,
                    "Partial Success",
                    f"Deleted {deleted_count} file(s), but {len(errors)} failed.",
                    informative_text="\n".join(errors[:5]) + ("\n..." if len(errors) > 5 else "")
                )

            self._refresh_analysis()

        def on_failure(error):
            progress.close()
            ms._log(f"Deletion failed: {error}")
            _show_dialog_centered_on_parent(
                self,
                QMessageBox.Icon.Critical,
                "Deletion Failed",
                f"Failed to delete files: {error}"
            )

        op = QueryOp(parent=self, op=do_delete, success=on_success)
        op.failure(on_failure)
        op.run_in_background()

    def _delete_files_from_anki(self, files: list[str]):
        if not mw or not mw.col:
            return

        media_dir = mw.col.media.dir()
        if not media_dir:
            _show_dialog_centered_on_parent(
                self,
                QMessageBox.Icon.Critical,
                "Error",
                "Anki media folder not available"
            )
            return

        total = len(files)
        progress = QProgressDialog("Deleting files from Anki media folder...", None, 0, 100, self)
        progress.setWindowTitle("Deleting Files")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)
        progress.show()

        def do_delete(col):
            deleted_count = 0
            errors = []
            last_percent = -1

            for i, filename in enumerate(files):
                percent = (i * 100) // total
                if percent > last_percent:
                    mw.taskman.run_on_main(lambda p=percent: progress.setValue(p))
                    last_percent = percent

                file_path = os.path.join(media_dir, filename)
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        deleted_count += 1
                except Exception as e:
                    ms._log(f"Failed to delete {filename}: {e}")
                    errors.append(f"{filename}: {e}")

            return {"deleted_count": deleted_count, "errors": errors}

        def on_success(result: dict):
            progress.close()
            errors = result["errors"]
            deleted_count = result["deleted_count"]

            if errors:
                _show_dialog_centered_on_parent(
                    self,
                    QMessageBox.Icon.Warning,
                    "Partial Success",
                    f"Deleted {deleted_count} file(s), but {len(errors)} failed.",
                    informative_text="\n".join(errors[:5]) + ("\n..." if len(errors) > 5 else "")
                )

            self._refresh_analysis()

        def on_failure(error):
            progress.close()
            ms._log(f"Deletion failed: {error}")
            _show_dialog_centered_on_parent(
                self,
                QMessageBox.Icon.Critical,
                "Deletion Failed",
                f"Failed to delete files: {error}"
            )

        op = QueryOp(parent=self, op=do_delete, success=on_success)
        op.failure(on_failure)
        op.run_in_background()

    @classmethod
    def show_dialog(cls, source_folder=None, parent=None) -> Optional[int]:
        """Show the media manager dialog (singleton).

        Runs analysis first with progress dialog, then shows the main dialog.

        Args:
            source_folder: Path to source media folder, or None to skip source analysis
            parent: Parent window (typically mw)
        """
        if cls._instance_open:
            ms._log("Dialog already open")
            return None

        if not parent:
            parent = mw

        cls._instance_open = True

        progress = QProgressDialog("Analyzing media files...", None, 0, 0, parent)
        progress.setWindowTitle("Please Wait")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)
        progress.show()

        analysis_result = None
        error_occurred = False

        from aqt.qt import QEventLoop
        loop = QEventLoop()

        def on_success(result: dict):
            nonlocal analysis_result
            progress.close()
            analysis_result = result
            ms._log("Analysis complete")
            loop.quit()

        def on_failure(error):
            nonlocal error_occurred
            progress.close()
            error_occurred = True
            ms._log(f"Analysis failed: {error}")
            _show_dialog_centered_on_parent(
                parent,
                QMessageBox.Icon.Critical,
                "Analysis Failed",
                f"Failed to analyze media files: {error}"
            )
            loop.quit()

        op = QueryOp(
            parent=parent,
            op=lambda col: ms.analyze_media_usage(source_folder=source_folder),
            success=on_success
        )
        op.failure(on_failure)
        op.run_in_background()

        loop.exec()

        if error_occurred or analysis_result is None:
            cls._instance_open = False
            return None

        dialog = cls(analysis_result, source_folder=source_folder, parent=parent)

        def on_finished():
            cls._instance_open = False

        qconnect(dialog.finished, on_finished)

        result = dialog.exec()

        return result

    @classmethod
    def show_dialog_with_results(cls, analysis_result: dict, source_folder=None, parent=None) -> Optional[int]:
        """Show the media manager dialog with pre-computed results (singleton)."""
        if cls._instance_open:
            ms._log("Dialog already open")
            return None

        if not parent:
            parent = mw

        cls._instance_open = True

        dialog = cls(analysis_result, source_folder=source_folder, parent=parent)

        def on_finished():
            cls._instance_open = False

        qconnect(dialog.finished, on_finished)
        result = dialog.exec()
        return result
