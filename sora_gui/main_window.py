"""Main application window"""
import os
import logging
from pathlib import Path
from typing import Optional, Tuple

import requests
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QFormLayout, QHBoxLayout, QGridLayout,
    QComboBox, QLineEdit, QTextEdit, QPushButton, QLabel, QFileDialog,
    QProgressBar, QPlainTextEdit, QMessageBox, QSplitter, QCheckBox, QSpinBox, QFrame, QSizePolicy, QScrollArea
)
from PySide6.QtCore import Qt, QSize, QThread, QUrl, QTimer, QPoint, QRect
from PySide6.QtGui import QDesktopServices, QGuiApplication
from shiboken6 import isValid

try:
    from PIL import Image
except ImportError:
    Image = None

from .constants import API_BASE, SUPPORTED_SIZES, SUPPORTED_SECONDS, TIMEOUT_TEST, TIMEOUT_MODERATION
from .config import OUTPUT_DIR, get_saved_key, set_saved_key, ensure_dirs
from .utils import safe_json, pretty, aspect_of, check_disk_space, validate_api_key
from sora_gui.preview import CompactPreviewRow
from .dialogs import JsonDialog
from .worker import Worker
from .assets import icon

logger = logging.getLogger(__name__)

class SoraApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setObjectName("Root")
        self.setWindowTitle("Sora Studio")
        self.setMinimumSize(QSize(1040, 820))
        self.last_response: Optional[dict] = None
        self.last_file: Optional[str] = None
        self.thread: Optional[QThread] = None
        self.worker: Optional[Worker] = None
        
        ensure_dirs()
        self._setup_ui()
        self._connect_signals()
        self._load_initial_state()
    
    def _setup_ui(self) -> None:
        """Setup the user interface"""
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.top_panel = self._create_top_panel()
        self.bottom_panel = self._create_bottom_panel()
        self.splitter.addWidget(self.top_panel)
        self.splitter.addWidget(self.bottom_panel)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, True)
        self.setCentralWidget(self.splitter)
    
    def _create_top_panel(self) -> QWidget:
        """Create top control panel"""
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        self.scroll_inner = QWidget()
        self.scroll_area.setWidget(self.scroll_inner)
        
        root = QVBoxLayout(self.scroll_inner)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)
        
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(12)
        
        self.model_box = QComboBox()
        self.model_box.addItems(["sora-2", "sora-2-pro"])
        form.addRow("Model", self.model_box)
        
        self.size_box = QComboBox()
        form.addRow("Size", self.size_box)
        
        self.seconds_box = QComboBox()
        self.seconds_box.addItems(SUPPORTED_SECONDS)
        form.addRow("Duration (s)", self.seconds_box)
        
        key_row = self._create_api_key_row()
        form.addRow("API Key", key_row)
        
        root.addLayout(form)
        
        self.preview_row = CompactPreviewRow(self.scroll_inner)
        self.preview_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.preview_row.setMaximumHeight(200)
        root.addWidget(self.preview_row)
        
        root.addSpacing(12)
        
        prompt_label = QLabel("Prompt")
        prompt_label.setProperty("heading", True)
        root.addWidget(prompt_label)
        
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("Insert your prompt here...")
        self.prompt_edit.setMinimumHeight(140)
        self.prompt_edit.setMaximumHeight(220)
        self.prompt_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        root.addWidget(self.prompt_edit)
        
        form2 = QFormLayout()
        form2.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form2.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form2.setVerticalSpacing(10)
        form2.setHorizontalSpacing(12)
        
        input_row = self._create_input_row()
        form2.addRow("Input Reference (optional)", input_row)
        
        out_row = self._create_output_row()
        form2.addRow("Output Folder", out_row)
        
        self.preflight_box = QCheckBox("Preflight moderation")
        self.preflight_box.setChecked(True)
        form2.addRow("Safety", self.preflight_box)
        
        poll_row = self._create_poll_row()
        form2.addRow("Polling", poll_row)
        
        jid_row = self._create_job_control_row()
        form2.addRow("Job Control", jid_row)
        
        root.addLayout(form2)
        
        btn_row = self._create_button_row()
        root.addLayout(btn_row)
        
        return self.scroll_area
    


    def _create_api_key_row(self) -> QHBoxLayout:
        """Create API key input row"""
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("sk-...")
        self.save_key_btn = QPushButton(icon("key.svg"), "Save Key")
        self.test_key_btn = QPushButton("Test Key")
        
        key_row = QHBoxLayout()
        key_row.setSpacing(8)
        key_row.addWidget(self.api_key_edit, 1)
        key_row.addWidget(self.save_key_btn)
        key_row.addWidget(self.test_key_btn)
        return key_row
    
    def _create_input_row(self) -> QHBoxLayout:
        """Create input file row"""
        self.input_edit = QLineEdit()
        self.input_browse = QPushButton(icon("image.svg"), "Browse…")
        
        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        input_row.addWidget(self.input_edit, 1)
        input_row.addWidget(self.input_browse)
        return input_row
    
    def _create_output_row(self) -> QHBoxLayout:
        """Create output directory row"""
        self.output_dir_edit = QLineEdit(str(OUTPUT_DIR))
        self.output_dir_btn = QPushButton(icon("folder.svg"), "Change…")
        
        out_row = QHBoxLayout()
        out_row.setSpacing(8)
        out_row.addWidget(self.output_dir_edit, 1)
        out_row.addWidget(self.output_dir_btn)
        return out_row
    
    def _create_poll_row(self) -> QHBoxLayout:
        """Create polling configuration row"""
        self.poll_spin = QSpinBox()
        self.poll_spin.setRange(1, 20)
        self.poll_spin.setValue(2)
        
        self.maxwait_spin = QSpinBox()
        self.maxwait_spin.setRange(1, 60)
        self.maxwait_spin.setValue(12)
        
        poll_row = QHBoxLayout()
        poll_row.addWidget(QLabel("Poll every (s)"))
        poll_row.addWidget(self.poll_spin)
        poll_row.addWidget(QLabel("Max wait (min)"))
        poll_row.addWidget(self.maxwait_spin)
        poll_row.addStretch(1)
        return poll_row
    
    def _create_job_control_row(self) -> QHBoxLayout:
        """Create job control row"""
        self.jobid_edit = QLineEdit()
        self.jobid_edit.setPlaceholderText("existing job id (optional)")
        self.resume_btn = QPushButton(icon("job.svg"), "Resume Job")
        self.copy_job_btn = QPushButton("Copy Job ID")
        
        jid_row = QHBoxLayout()
        jid_row.setSpacing(8)
        jid_row.addWidget(self.jobid_edit, 1)
        jid_row.addWidget(self.resume_btn)
        jid_row.addWidget(self.copy_job_btn)
        return jid_row
    
    def _create_button_row(self) -> QHBoxLayout:
        """Create main action button row"""
        self.send_btn = QPushButton(icon("play.svg"), "Generate")
        self.send_btn.setProperty("variant", "primary")
        self.open_last_btn = QPushButton(icon("open.svg"), "Open Last File")
        self.open_last_btn.setEnabled(False)
        self.show_resp_btn = QPushButton(icon("settings.svg"), "Show Last Response")
        self.show_resp_btn.setEnabled(False)
        self.show_resp_btn.setProperty("variant", "ghost")
        
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addWidget(self.send_btn)
        btn_row.addWidget(self.open_last_btn)
        btn_row.addWidget(self.show_resp_btn)
        return btn_row
    
    def _create_bottom_panel(self) -> QWidget:
        """Create bottom log panel"""
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setMinimumHeight(32)
        
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(10)
        
        bottom = QFrame()
        bottom.setProperty("card", True)
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(20, 20, 20, 20)
        bottom_layout.setSpacing(12)
        bottom_layout.addWidget(self.progress)
        bottom_layout.addWidget(self.log, 1)
        return bottom
    
    def _connect_signals(self) -> None:
        """Connect all signal handlers"""
        self.model_box.currentTextChanged.connect(self.refresh_sizes)
        self.size_box.currentTextChanged.connect(self.on_size_change)
        self.size_box.currentTextChanged.connect(lambda: QTimer.singleShot(50, self._layout_self_check_now))
        self.input_browse.clicked.connect(self.browse_input)
        self.output_dir_btn.clicked.connect(self.browse_output)
        self.save_key_btn.clicked.connect(self.save_key)
        self.test_key_btn.clicked.connect(self.test_key)
        self.send_btn.clicked.connect(self.generate)
        self.show_resp_btn.clicked.connect(self.show_last_response)
        self.open_last_btn.clicked.connect(self.open_last_file)
        self.resume_btn.clicked.connect(self.resume_job)
        self.copy_job_btn.clicked.connect(self.copy_job_id)
    
    def _load_initial_state(self) -> None:
        """Load initial application state"""
        self.api_key_edit.setText(get_saved_key())
        self.refresh_sizes()
        self.on_size_change(self.size_box.currentText())
        QTimer.singleShot(500, self._layout_self_check_now)
    
    def resizeEvent(self, e) -> None:
        """Handle window resize"""
        super().resizeEvent(e)
        QTimer.singleShot(50, self._layout_self_check_now)
    
    def _global_rect(self, w):
        """Get widget rect relative to main window"""
        if not w or not isValid(w):
            return QRect()
        try:
            if not w.isVisible():
                return QRect()
            geom = w.geometry()
            parent = w.parent()
            while parent and parent != self and isValid(parent):
                parent_geom = parent.geometry()
                geom.translate(parent_geom.x(), parent_geom.y())
                parent = parent.parent()
            return geom
        except:
            return QRect()
    
    def _layout_self_check_now(self):
        """Validate layout and show error banner if issues detected"""
        if not hasattr(self, 'preview_row') or not hasattr(self, 'prompt_edit'):
            return
        
        if not self.isVisible():
            return
        
        if not isValid(self.preview_row) or not isValid(self.preview_row.card) or not isValid(self.prompt_edit):
            return
        
        try:
            card = self._global_rect(self.preview_row.card)
            pr = self._global_rect(self.preview_row.canvas)
            prompt = self._global_rect(self.prompt_edit)
            
            if card.isEmpty() or pr.isEmpty() or prompt.isEmpty():
                return
            
            overlap = card.bottom() + 8 > prompt.top()
            too_small = card.height() > 220
            
            if overlap or too_small:
                if not hasattr(self, "_error_banner"):
                    self._error_banner = QLabel(f"Layout error: preview overlapping or too large (card_bottom={card.bottom()}, prompt_top={prompt.top()}, card_h={card.height()})")
                    self._error_banner.setStyleSheet("background:#EF4444;color:white;padding:6px 10px;border-radius:8px;font-weight:600;")
                    self.statusBar().addPermanentWidget(self._error_banner)
                    self._error_banner.show()
                
                ss = self.grab()
                from pathlib import Path
                out = Path.cwd() / "layout_failure.png"
                ss.save(str(out))
                logger.error(f"Layout validation failed: overlap={overlap}, too_large={too_small}, card_bottom={card.bottom()}, prompt_top={prompt.top()}, card_h={card.height()}, saved to {out}")
            else:
                if hasattr(self, "_error_banner"):
                    self.statusBar().removeWidget(self._error_banner)
                    self._error_banner.deleteLater()
                    del self._error_banner
                logger.info(f"Layout validation passed: card_bottom={card.bottom()}, prompt_top={prompt.top()}, gap={prompt.top() - card.bottom()}, card_h={card.height()}")
        except Exception as e:
            import traceback
            logger.error(f"Layout self-check exception: {e}\n{traceback.format_exc()}")

    def on_size_change(self, size_str: str) -> None:
        """Handle size combo box change"""
        if size_str:
            w, h = self._parse_size(size_str)
            self.preview_row.set_dimensions(w, h)
    
    def _parse_size(self, text: str) -> tuple:
        """Parse size string like '1280x720' into (w, h)"""
        try:
            parts = text.lower().split("x")
            w, h = int(parts[0]), int(parts[1])
            return w, h
        except:
            return 1280, 720

    def refresh_sizes(self) -> None:
        """Refresh available sizes based on selected model"""
        m = self.model_box.currentText()
        sizes = SUPPORTED_SIZES.get(m, [])
        cur = self.size_box.currentText()
        self.size_box.blockSignals(True)
        self.size_box.clear()
        self.size_box.addItems(sizes)
        self.size_box.blockSignals(False)
        if cur in sizes:
            self.size_box.setCurrentText(cur)
        self.on_size_change(self.size_box.currentText())

    def browse_input(self) -> None:
        """Browse for input reference image"""
        p, _ = QFileDialog.getOpenFileName(
            self, 
            "Choose Image Reference", 
            str(Path.home()), 
            "Images (*.png *.jpg *.jpeg *.webp);;All Files (*)"
        )
        if p:
            self.input_edit.setText(p)

    def browse_output(self) -> None:
        """Browse for output directory"""
        d = QFileDialog.getExistingDirectory(
            self, 
            "Choose Output Folder", 
            self.output_dir_edit.text()
        )
        if d:
            self.output_dir_edit.setText(d)

    def save_key(self) -> None:
        """Save API key"""
        k = self.api_key_edit.text().strip()
        if not k:
            QMessageBox.warning(self, "Missing", "Enter an API key first.")
            return
        
        if not validate_api_key(k):
            QMessageBox.warning(
                self, 
                "Invalid Key", 
                "API key should start with 'sk-' and be at least 20 characters."
            )
            return
        
        set_saved_key(k)
        QMessageBox.information(self, "Saved", "API key saved securely.")

    def test_key(self) -> None:
        """Test API key validity"""
        k = self.api_key_edit.text().strip()
        if not k:
            QMessageBox.warning(self, "Missing", "Enter an API key first.")
            return
        
        if not validate_api_key(k):
            QMessageBox.warning(
                self, 
                "Invalid Key", 
                "API key format looks incorrect. It should start with 'sk-'."
            )
            return
        
        try:
            r = requests.get(
                f"{API_BASE}/models", 
                headers={"Authorization": f"Bearer {k}"}, 
                timeout=TIMEOUT_TEST
            )
            self.last_response = {
                "endpoint": "GET /models", 
                "status": r.status_code, 
                "body": safe_json(r)
            }
            self.show_resp_btn.setEnabled(True)
            
            if r.status_code == 200:
                QMessageBox.information(self, "Success", "API key is valid!")
            elif r.status_code == 401:
                QMessageBox.warning(self, "Invalid", "API key is not authorized.")
            else:
                QMessageBox.warning(
                    self, 
                    "Error", 
                    f"Status {r.status_code}: {r.text[:400]}"
                )
        except requests.exceptions.Timeout:
            QMessageBox.critical(self, "Timeout", "Request timed out. Check your internet connection.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Test key failed: {e}")
            QMessageBox.critical(self, "Network Error", f"Failed to connect: {str(e)}")

    def show_last_response(self) -> None:
        """Show last API response in dialog"""
        if self.last_response is None:
            QMessageBox.information(self, "Info", "No response captured yet.")
            return
        dlg = JsonDialog("Last API Response", self.last_response)
        dlg.exec()

    def run_moderation_check(self, api_key: str, prompt: str) -> Tuple[bool, list]:
        """Run content moderation check on prompt"""
        try:
            r = requests.post(
                f"{API_BASE}/moderations", 
                headers={
                    "Authorization": f"Bearer {api_key}", 
                    "Content-Type": "application/json"
                }, 
                json={"model": "omni-moderation-latest", "input": prompt}, 
                timeout=TIMEOUT_MODERATION
            )
            self.last_response = {
                "endpoint": "POST /moderations", 
                "status": r.status_code, 
                "body": safe_json(r)
            }
            self.show_resp_btn.setEnabled(True)
            
            if r.status_code != 200:
                logger.warning(f"Moderation check failed: {r.status_code}")
                return True, ["moderation_request_failed"]
            
            body = r.json()
            res = body.get("results", [{}])[0]
            flagged = res.get("flagged", False)
            cats = res.get("categories", {}) or {}
            reasons = [k for k, v in cats.items() if v]
            return flagged, reasons
        except requests.exceptions.Timeout:
            logger.error("Moderation check timed out")
            return True, ["moderation_timeout"]
        except Exception as e:
            logger.exception("Moderation check failed")
            return True, [f"moderation_error: {str(e)}"]

    def start_worker(self, job_id: Optional[str] = None) -> None:
        """Start worker thread for video generation"""
        k = self.api_key_edit.text().strip()
        m = self.model_box.currentText()
        size = self.size_box.currentText()
        sec = self.seconds_box.currentText()
        prompt = self.prompt_edit.toPlainText().strip()
        ref_path = self.input_edit.text().strip()
        out_dir = Path(self.output_dir_edit.text().strip() or str(OUTPUT_DIR))
        
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create output directory: {e}")
            QMessageBox.critical(
                self, 
                "Error", 
                f"Cannot create output directory:\n{str(e)}"
            )
            return
        
        if not check_disk_space(str(out_dir)):
            reply = QMessageBox.question(
                self,
                "Low Disk Space",
                "Less than 5GB free space available. Continue anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        
        self.progress.setValue(0)
        self.log.clear()
        self.send_btn.setEnabled(False)
        
        self.thread = QThread()
        self.worker = Worker(
            k, m, size, sec, prompt, ref_path, 
            str(out_dir), job_id, 
            self.poll_spin.value(), 
            self.maxwait_spin.value()
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progressed.connect(self.progress.setValue)
        self.worker.logged.connect(self.log.appendPlainText)
        self.worker.lastresp.connect(self.capture_last_response)
        self.worker.saved.connect(self.on_saved)
        self.worker.finished.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.worker.jobid.connect(self.on_jobid)
        self.thread.start()

    def generate(self) -> None:
        """Start video generation"""
        k = self.api_key_edit.text().strip()
        if not k:
            QMessageBox.warning(self, "Missing API Key", "Please enter and save your API key first.")
            return
        
        if not validate_api_key(k):
            QMessageBox.warning(
                self, 
                "Invalid API Key", 
                "API key format appears incorrect. It should start with 'sk-'."
            )
            return
        
        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Missing Prompt", "Please enter a prompt describing the video you want to generate.")
            return
        
        if self.preflight_box.isChecked():
            flagged, reasons = self.run_moderation_check(k, prompt)
            if flagged:
                QMessageBox.warning(
                    self, 
                    "Content Policy Violation", 
                    f"Prompt flagged by moderation:\n{', '.join(reasons) or 'unspecified'}\n\n"
                    "Please revise your prompt to comply with OpenAI's usage policies."
                )
                return
        
        ref_path = self.input_edit.text().strip()
        size = self.size_box.currentText()
        
        if ref_path and Image:
            if not os.path.isfile(ref_path):
                QMessageBox.warning(self, "File Not Found", f"Reference image not found:\n{ref_path}")
                return
            
            try:
                w, h = aspect_of(size)
                im = Image.open(ref_path)
                iw, ih = im.size
                if iw != w or ih != h:
                    reply = QMessageBox.question(
                        self, 
                        "Resolution Mismatch", 
                        f"Image resolution ({iw}x{ih}) doesn't match target ({w}x{h}).\n\n"
                        "The image will be automatically adjusted, which may affect quality.\n\n"
                        "Continue anyway?"
                    )
                    if reply != QMessageBox.Yes:
                        return
            except Exception as e:
                logger.error(f"Failed to check image: {e}")
                QMessageBox.warning(
                    self, 
                    "Image Error", 
                    f"Could not read reference image:\n{str(e)}"
                )
                return
        
        self.start_worker(job_id=None)

    def resume_job(self) -> None:
        """Resume existing job by ID"""
        k = self.api_key_edit.text().strip()
        if not k:
            QMessageBox.warning(self, "Missing API Key", "Please enter and save your API key first.")
            return
        
        if not validate_api_key(k):
            QMessageBox.warning(
                self, 
                "Invalid API Key", 
                "API key format appears incorrect. It should start with 'sk-'."
            )
            return
        
        jid = self.jobid_edit.text().strip()
        if not jid:
            QMessageBox.warning(self, "Missing Job ID", "Please enter a job ID to resume.")
            return
        
        self.start_worker(job_id=jid)

    def capture_last_response(self, payload: dict) -> None:
        """Capture API response for debugging"""
        self.last_response = payload
        self.show_resp_btn.setEnabled(True)

    def on_saved(self, path: str) -> None:
        """Handle video save completion"""
        self.last_file = path
        self.open_last_btn.setEnabled(True)
        self.log.appendPlainText(f"Saved: {path}")

    def on_finished(self) -> None:
        """Handle worker completion"""
        self.send_btn.setEnabled(True)
        if self.thread:
            self.thread.quit()
            self.thread.wait()
            self.thread = None
            self.worker = None
        self.progress.setValue(100)

    def on_failed(self, msg: str) -> None:
        """Handle worker failure"""
        self.log.appendPlainText("Generation failed.")
        self.log.appendPlainText(str(msg))
        self.send_btn.setEnabled(True)
        if self.thread:
            self.thread.quit()
            self.thread.wait()
            self.thread = None
            self.worker = None

    def on_jobid(self, jid: str) -> None:
        """Handle job ID received"""
        self.jobid_edit.setText(jid)

    def open_last_file(self) -> None:
        """Open last generated video file"""
        if self.last_file and os.path.isfile(self.last_file):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_file))
        elif self.last_file:
            QMessageBox.warning(self, "File Not Found", f"Video file no longer exists:\n{self.last_file}")

    def copy_job_id(self) -> None:
        """Copy job ID to clipboard"""
        txt = self.jobid_edit.text().strip()
        if not txt:
            return
        QGuiApplication.clipboard().setText(txt)
        self.log.appendPlainText(f"Copied job ID: {txt}")
