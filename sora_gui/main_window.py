"""Main application window"""
import os
import logging
from pathlib import Path
from typing import Optional, Tuple

import requests
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QFormLayout, QHBoxLayout, QGridLayout,
    QComboBox, QLineEdit, QTextEdit, QPushButton, QLabel, QFileDialog,
    QProgressBar, QPlainTextEdit, QMessageBox, QSplitter, QCheckBox, QSpinBox, QFrame, QSizePolicy, QScrollArea,
    QTabWidget, QMenu
)
from PySide6.QtCore import Qt, QTimer, QThread, QSize, QUrl, QMetaObject, Q_ARG, QPoint, QRect
from PySide6.QtGui import QDesktopServices, QGuiApplication
from shiboken6 import isValid

try:
    from PIL import Image
except ImportError:
    Image = None

from .constants import API_BASE, SUPPORTED_SIZES, SUPPORTED_SECONDS, TIMEOUT_TEST, TIMEOUT_MODERATION
from .config import OUTPUT_DIR, get_saved_key, set_saved_key, ensure_dirs, load_config, save_config
from .utils import safe_json, pretty, aspect_of, check_disk_space, validate_api_key
from sora_gui.preview import CompactPreviewRow
from .dialogs import JsonDialog
from .worker import Worker
from .assets import icon
from sora_core.models import Project, Settings, Shot, Template
from sora_core.queue import QueueManager
from .config import get_settings, save_settings, get_last_state, save_last_state, get_recent_projects, add_recent_project, CONFIG_DIR, get_window_geometry, save_window_geometry
from .queue_panel import QueuePanel
from .template_panel import TemplatePanel
import uuid

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
        self.current_project: Optional[Project] = None
        self.current_project_path: Optional[Path] = None
        self.autosave_timer: Optional[QTimer] = None
        self.project_modified: bool = False
        self.queue_manager: Optional[QueueManager] = None
        self.queue_panel: Optional[QueuePanel] = None
        self.template_panel: Optional[TemplatePanel] = None
        self.queue_running: bool = False
        self.prompt_history: list[str] = []
        
        ensure_dirs()
        self._setup_ui()
        self._setup_menu()
        self._connect_signals()
        self._load_initial_state()
        self._setup_autosave()
        self._restore_geometry()
        
        if not self.current_project:
            self.current_project = Project(
                name="Untitled Project",
                output_dir=str(OUTPUT_DIR),
                settings=Settings(**get_settings())
            )
            self._update_window_title()
    
    def _restore_geometry(self) -> None:
        """Restore window geometry"""
        geometry = get_window_geometry()
        if geometry:
            if "window_geometry" in geometry:
                try:
                    self.restoreGeometry(bytes.fromhex(geometry["window_geometry"]))
                except Exception as e:
                    logger.warning(f"Failed to restore window geometry: {e}")
            if "splitter_state" in geometry:
                try:
                    self.centralWidget().restoreState(bytes.fromhex(geometry["splitter_state"]))
                except Exception as e:
                    logger.warning(f"Failed to restore splitter state: {e}")
            if "left_splitter_sizes" in geometry and geometry["left_splitter_sizes"]:
                try:
                    QTimer.singleShot(100, lambda: self._restore_left_splitter(geometry["left_splitter_sizes"]))
                except Exception as e:
                    logger.warning(f"Failed to restore left splitter: {e}")
    
    def _restore_left_splitter(self, sizes) -> None:
        """Restore left splitter sizes"""
        if hasattr(self, 'top_panel') and hasattr(self, 'bottom_panel'):
            parent = self.top_panel.parent()
            if isinstance(parent, QSplitter):
                parent.setSizes(sizes)
                logger.info(f"Restored left splitter sizes: {sizes}")
    
    def _setup_ui(self) -> None:
        """Setup the user interface"""
        self.queue_manager = QueueManager(
            parallel_jobs=1,
            state_file=CONFIG_DIR / "queue_state.json",
            worker_factory=self._process_queue_shot
        )
        
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        left_splitter = QSplitter(Qt.Orientation.Vertical)
        self.top_panel = self._create_top_panel()
        self.bottom_panel = self._create_bottom_panel()
        left_splitter.addWidget(self.top_panel)
        left_splitter.addWidget(self.bottom_panel)
        left_splitter.setStretchFactor(0, 3)
        left_splitter.setStretchFactor(1, 1)
        left_splitter.setCollapsible(0, False)
        left_splitter.setCollapsible(1, True)
        
        right_tabs = self._create_right_tabs()
        
        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(right_tabs)
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setCollapsible(0, False)
        main_splitter.setCollapsible(1, False)
        
        self.setCentralWidget(main_splitter)
    
    def _create_right_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        
        self.queue_panel = QueuePanel(self)
        self.queue_panel.set_queue_manager(self.queue_manager)
        tabs.addTab(self.queue_panel, "Queue")
        
        self.template_panel = TemplatePanel(self)
        self.template_panel.main_window = self
        self.template_panel.template_applied.connect(self._on_template_prompt_applied)
        tabs.addTab(self.template_panel, "Templates")
        
        return tabs
    
    def _on_template_prompt_applied(self, prompt: str):
        self.prompt_edit.setPlainText(prompt)
        self._mark_modified()
    
    def apply_template(self, template: Template):
        idx = self.model_box.findText(template.model)
        if idx >= 0:
            self.model_box.setCurrentIndex(idx)
        
        size_str = f"{template.width}x{template.height}"
        idx = self.size_box.findText(size_str)
        if idx >= 0:
            self.size_box.setCurrentIndex(idx)
        
        idx = self.seconds_box.findText(str(template.duration_s))
        if idx >= 0:
            self.seconds_box.setCurrentIndex(idx)
        
        self.prompt_edit.setPlainText(template.prompt)
        self._mark_modified()
        self.log.appendPlainText(f"Applied template: {template.name}")
    
    def _setup_menu(self) -> None:
        """Setup menu bar"""
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("&File")
        
        new_action = file_menu.addAction("&New Project")
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_project)
        
        open_action = file_menu.addAction("&Open Project...")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_project)
        
        self.recent_menu = file_menu.addMenu("Open &Recent")
        self._update_recent_menu()
        
        file_menu.addSeparator()
        
        save_action = file_menu.addAction("&Save Project")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_project)
        
        save_as_action = file_menu.addAction("Save Project &As...")
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_project_as)
        
        file_menu.addSeparator()
        
        quit_action = file_menu.addAction("&Quit")
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
    
    def _update_recent_menu(self) -> None:
        """Update recent projects menu"""
        self.recent_menu.clear()
        recent = get_recent_projects()
        
        if not recent:
            action = self.recent_menu.addAction("No recent projects")
            action.setEnabled(False)
            return
        
        for project_path in recent:
            if Path(project_path).exists():
                action = self.recent_menu.addAction(Path(project_path).name)
                action.triggered.connect(lambda checked, p=project_path: self.open_project_path(p))
    
    def _setup_autosave(self) -> None:
        """Setup autosave timer"""
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self._autosave)
        self.autosave_timer.start(30000)
    
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
        
        prompt_header = QHBoxLayout()
        prompt_header.setSpacing(8)
        
        self.history_btn = QPushButton("Recent ▼")
        self.history_btn.clicked.connect(self._show_history_menu)
        prompt_header.addStretch()
        prompt_header.addWidget(self.history_btn)
        
        root.addLayout(prompt_header)
        
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
        self.queue_btn = QPushButton("➕ Add to Queue")
        
        self.send_btn = QPushButton(icon("play.svg"), "Generate Now")
        self.send_btn.setProperty("variant", "primary")
        self.open_last_btn = QPushButton(icon("open.svg"), "Open Last File")
        self.open_last_btn.setEnabled(False)
        self.show_resp_btn = QPushButton(icon("settings.svg"), "Show Last Response")
        self.show_resp_btn.setEnabled(False)
        self.show_resp_btn.setProperty("variant", "ghost")
        
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addWidget(self.queue_btn)
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
        self.queue_btn.clicked.connect(self.add_to_queue)
        self.send_btn.clicked.connect(self.generate_or_stop)
        self.show_resp_btn.clicked.connect(self.show_last_response)
        self.open_last_btn.clicked.connect(self.open_last_file)
        self.resume_btn.clicked.connect(self.resume_job)
        self.copy_job_btn.clicked.connect(self.copy_job_id)
    
    def _show_history_menu(self):
        menu = QMenu(self)
        
        if not self.prompt_history:
            action = menu.addAction("No recent prompts")
            action.setEnabled(False)
        else:
            for prompt in self.prompt_history[:10]:
                preview = prompt[:60] + "..." if len(prompt) > 60 else prompt
                action = menu.addAction(preview)
                action.triggered.connect(lambda checked, p=prompt: self._apply_history_prompt(p))
            
            if len(self.prompt_history) > 0:
                menu.addSeparator()
                clear_action = menu.addAction("Clear History")
                clear_action.triggered.connect(self._clear_history)
        
        menu.exec(self.history_btn.mapToGlobal(self.history_btn.rect().bottomLeft()))
    
    def _apply_history_prompt(self, prompt: str):
        self.prompt_edit.setPlainText(prompt)
        self._mark_modified()
    
    def _clear_history(self):
        self.prompt_history.clear()
        self._save_prompt_history()
    
    def _add_to_history(self, prompt: str):
        if not prompt or not prompt.strip():
            return
        
        if prompt in self.prompt_history:
            self.prompt_history.remove(prompt)
        
        self.prompt_history.insert(0, prompt)
        self.prompt_history = self.prompt_history[:20]
        self._save_prompt_history()
    
    def _save_prompt_history(self):
        cfg = load_config()
        cfg["prompt_history"] = self.prompt_history
        save_config(cfg)
    
    def _load_prompt_history(self):
        cfg = load_config()
        self.prompt_history = cfg.get("prompt_history", [])
    
    def _load_initial_state(self) -> None:
        self.api_key_edit.setText(get_saved_key())
        self.refresh_sizes()
        
        self._load_prompt_history()
        
        last_state = get_last_state()
        if last_state:
            if "model" in last_state:
                idx = self.model_box.findText(last_state["model"])
                if idx >= 0:
                    self.model_box.setCurrentIndex(idx)
            if "size" in last_state:
                idx = self.size_box.findText(last_state["size"])
                if idx >= 0:
                    self.size_box.setCurrentIndex(idx)
            if "duration" in last_state:
                idx = self.seconds_box.findText(last_state["duration"])
                if idx >= 0:
                    self.seconds_box.setCurrentIndex(idx)
            if "prompt" in last_state and last_state["prompt"]:
                self.prompt_edit.setPlainText(last_state["prompt"])
        
        self.on_size_change(self.size_box.currentText())
        
        self.model_box.currentTextChanged.connect(lambda: self._mark_modified())
        self.size_box.currentTextChanged.connect(lambda: self._mark_modified())
        self.seconds_box.currentTextChanged.connect(lambda: self._mark_modified())
        self.prompt_edit.textChanged.connect(lambda: self._mark_modified())
        self.output_dir_edit.textChanged.connect(lambda: self._mark_modified())
        
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
        except Exception:
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
        """Parse size string like '1280x720' into (w, h) using utils.aspect_of with safe fallback"""
        try:
            return aspect_of(text)
        except ValueError:
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

    def generate_or_stop(self) -> None:
        """Generate videos or stop queue based on current state"""
        if self.queue_running:
            self.queue_manager.stop()
            self.queue_running = False
            self.send_btn.setText("⚡ Generate Now")
            self.log.appendPlainText("Queue stopped")
            return
        
        self.generate()
    
    def generate(self) -> None:
        """Start video generation - processes queue if items exist, otherwise uses current prompt"""
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
        
        status = self.queue_manager.get_queue_status()
        total_queued = len(status['queued']) + len(status['active'])
        
        if total_queued > 0:
            self.log.appendPlainText(f"Starting queue with {total_queued} items...")
            self.send_btn.setText("⏹ Stop Queue")
            self.queue_running = True
            if not self.queue_manager._running:
                self.queue_manager.start()
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
        
        self._add_to_history(prompt)
        
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
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Resume Job")
        msg_box.setText(f"How would you like to resume job {jid}?")
        msg_box.setIcon(QMessageBox.Icon.Question)
        
        resume_now_btn = msg_box.addButton("Resume Now (Immediate)", QMessageBox.ButtonRole.YesRole)
        add_queue_btn = msg_box.addButton("Add to Queue", QMessageBox.ButtonRole.NoRole)
        cancel_btn = msg_box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.exec()
        clicked = msg_box.clickedButton()
        
        if clicked == cancel_btn:
            return
        elif clicked == add_queue_btn:
            import uuid
            shot = Shot(
                id=str(uuid.uuid4()),
                model=self.model_box.currentText(),
                width=int(self.size_box.currentText().split("x")[0]),
                height=int(self.size_box.currentText().split("x")[1]),
                duration_s=int(self.seconds_box.currentText()),
                prompt=self.prompt_edit.toPlainText().strip() or f"Resume job {jid}",
                status="queued",
                job_id=jid
            )
            self.queue_manager.enqueue(shot)
            self.log.appendPlainText(f"Added job {jid} to queue")
        else:
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
    
    def add_to_queue(self) -> None:
        """Add current parameters to queue"""
        model = self.model_box.currentText()
        size = self.size_box.currentText()
        duration = int(self.seconds_box.currentText())
        prompt = self.prompt_edit.toPlainText().strip()
        
        if not prompt:
            QMessageBox.warning(self, "Missing Prompt", "Please enter a prompt.")
            return
        
        w, h = map(int, size.split("x"))
        
        shot = Shot(
            id=str(uuid.uuid4()),
            model=model,
            width=w,
            height=h,
            duration_s=duration,
            prompt=prompt,
            status="queued"
        )
        
        self.queue_manager.enqueue(shot)
        self.log.appendPlainText(f"Added to queue: {prompt[:50]}...")
        
        self._add_to_history(prompt)
        
        if self.current_project:
            self.current_project.shots.append(shot)
            self._mark_modified()
    
    def _process_queue_shot(self, shot: Shot) -> Tuple[bool, Optional[str]]:
        """Process a shot from the queue - called by queue worker thread"""
        try:
            from sora_gui.worker import Worker
            
            k = self.api_key_edit.text().strip()
            out_dir = Path(self.output_dir_edit.text().strip() or str(OUTPUT_DIR))
            out_dir.mkdir(parents=True, exist_ok=True)
            
            size_str = f"{shot.width}x{shot.height}"
            duration_str = str(shot.duration_s)
            
            QMetaObject.invokeMethod(
                self.log, "appendPlainText",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, f"\n--- Processing: {shot.prompt[:60]} ---")
            )
            QMetaObject.invokeMethod(
                self.progress, "setValue",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(int, 0)
            )
            
            resume_job_id = getattr(shot, 'job_id', None)
            
            worker = Worker(
                k, shot.model, size_str, duration_str, shot.prompt,
                "", out_dir, resume_job_id,
                self.poll_spin.value(),
                self.maxwait_spin.value()
            )
            
            result = {"success": False, "error": None}
            
            def on_progress(val):
                QMetaObject.invokeMethod(
                    self.progress, "setValue",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(int, val)
                )
            
            def on_log(msg):
                QMetaObject.invokeMethod(
                    self.log, "appendPlainText",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, msg)
                )
            
            def on_finished():
                result["success"] = True
            
            def on_failed(msg):
                result["error"] = str(msg)
            
            def on_saved(path):
                if path:
                    shot.output_path = str(path)
                    logger.info(f"Set output_path for shot {shot.id}: {shot.output_path}")
                QMetaObject.invokeMethod(
                    self.log, "appendPlainText",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, f"Saved: {path}")
                )
            
            def on_jobid(jid):
                QMetaObject.invokeMethod(
                    self.jobid_edit, "setText",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, jid)
                )
            
            def on_lastresp(resp):
                self.last_response = resp
                QMetaObject.invokeMethod(
                    self.show_resp_btn, "setEnabled",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(bool, True)
                )
            
            worker.progressed.connect(on_progress)
            worker.logged.connect(on_log)
            worker.finished.connect(on_finished)
            worker.failed.connect(on_failed)
            worker.saved.connect(on_saved)
            worker.jobid.connect(on_jobid)
            worker.lastresp.connect(on_lastresp)
            
            worker.run()
            
            QMetaObject.invokeMethod(
                self.progress, "setValue",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(int, 100)
            )
            
            if result["success"]:
                return (True, None)
            else:
                return (False, result.get("error", "Unknown error"))
                
        except Exception as e:
            logger.error(f"Failed to process shot: {e}")
            return (False, str(e))
    
    def new_project(self) -> None:
        """Create a new project"""
        if self.project_modified and self.current_project:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "Save current project before creating a new one?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Yes:
                if not self.save_project():
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        
        self.current_project = Project(
            name="Untitled Project",
            output_dir=str(OUTPUT_DIR),
            settings=Settings(**get_settings())
        )
        self.current_project_path = None
        self.project_modified = False
        
        if self.template_panel:
            self.template_panel._filter_templates()
        
        self._update_window_title()
        self.log.appendPlainText("Created new project")
    
    def open_project(self) -> None:
        """Open a project file"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            str(Path.home()),
            "Sora Studio Projects (*.sorastudio);;All Files (*)"
        )
        if path:
            self.open_project_path(path)
    
    def open_project_path(self, path: str) -> None:
        """Open a specific project file"""
        try:
            project_path = Path(path)
            self.current_project = Project.load(project_path)
            self.current_project_path = project_path
            self.project_modified = False
            self._restore_project_state()
            add_recent_project(str(project_path))
            self._update_recent_menu()
            self._update_window_title()
            self.log.appendPlainText(f"Opened project: {project_path.name}")
        except Exception as e:
            logger.error(f"Failed to open project: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open project:\n{e}")
    
    def save_project(self) -> bool:
        """Save current project"""
        if not self.current_project:
            return self.save_project_as()
        
        if not self.current_project_path:
            return self.save_project_as()
        
        try:
            self._capture_current_state()
            self.current_project.save(self.current_project_path)
            self.project_modified = False
            self._update_window_title()
            self.log.appendPlainText(f"Saved project: {self.current_project_path.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to save project: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save project:\n{e}")
            return False
    
    def save_project_as(self) -> bool:
        """Save project with a new name"""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project As",
            str(Path.home() / "untitled.sorastudio"),
            "Sora Studio Projects (*.sorastudio);;All Files (*)"
        )
        if not path:
            return False
        
        project_path = Path(path)
        if not project_path.suffix:
            project_path = project_path.with_suffix(".sorastudio")
        
        try:
            if not self.current_project:
                self.current_project = Project(
                    name=project_path.stem,
                    output_dir=str(OUTPUT_DIR),
                    settings=Settings(**get_settings())
                )
            
            self.current_project.name = project_path.stem
            self._capture_current_state()
            self.current_project.save(project_path)
            self.current_project_path = project_path
            self.project_modified = False
            add_recent_project(str(project_path))
            self._update_recent_menu()
            self._update_window_title()
            self.log.appendPlainText(f"Saved project: {project_path.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to save project: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save project:\n{e}")
            return False
    
    def _autosave(self) -> None:
        """Autosave current project"""
        if self.project_modified and self.current_project and self.current_project_path:
            try:
                self._capture_current_state()
                self.current_project.save(self.current_project_path)
                logger.info(f"Autosaved project: {self.current_project_path.name}")
            except Exception as e:
                logger.error(f"Autosave failed: {e}")
    
    def _capture_current_state(self) -> None:
        if not self.current_project:
            return
        
        self.current_project.current_model = self.model_box.currentText()
        self.current_project.current_size = self.size_box.currentText()
        self.current_project.current_duration = int(self.seconds_box.currentText())
        self.current_project.current_prompt = self.prompt_edit.toPlainText()
        self.current_project.output_dir = self.output_dir_edit.text()
    
    def _restore_project_state(self) -> None:
        if not self.current_project:
            return
        
        if self.current_project.current_model:
            idx = self.model_box.findText(self.current_project.current_model)
            if idx >= 0:
                self.model_box.setCurrentIndex(idx)
        
        if self.current_project.current_size:
            idx = self.size_box.findText(self.current_project.current_size)
            if idx >= 0:
                self.size_box.setCurrentIndex(idx)
        
        if self.current_project.current_duration:
            idx = self.seconds_box.findText(str(self.current_project.current_duration))
            if idx >= 0:
                self.seconds_box.setCurrentIndex(idx)
        
        if self.current_project.current_prompt:
            self.prompt_edit.setPlainText(self.current_project.current_prompt)
        
        if self.current_project.output_dir:
            self.output_dir_edit.setText(self.current_project.output_dir)
    
    def _update_window_title(self) -> None:
        """Update window title with project name"""
        title = "Sora Studio"
        if self.current_project:
            title = f"{self.current_project.name} - Sora Studio"
            if self.project_modified:
                title = f"*{title}"
        self.setWindowTitle(title)
    
    def _mark_modified(self) -> None:
        """Mark project as modified"""
        self.project_modified = True
        self._update_window_title()
    
    def closeEvent(self, event) -> None:
        """Handle window close"""
        if self.project_modified and self.current_project:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "Save project before closing?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Yes:
                if not self.save_project():
                    event.ignore()
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        
        save_last_state({
            "model": self.model_box.currentText(),
            "size": self.size_box.currentText(),
            "duration": self.seconds_box.currentText(),
            "prompt": self.prompt_edit.toPlainText()
        })
        
        try:
            geom = self.saveGeometry()
            main_state = self.centralWidget().saveState()
            
            left_splitter_sizes = []
            if hasattr(self, 'top_panel') and hasattr(self, 'bottom_panel'):
                parent = self.top_panel.parent()
                if isinstance(parent, QSplitter):
                    left_splitter_sizes = parent.sizes()
            
            save_window_geometry({
                "window_geometry": geom.toHex().data().decode(),
                "splitter_state": main_state.toHex().data().decode(),
                "left_splitter_sizes": left_splitter_sizes
            })
            logger.info("Saved window geometry")
        except Exception as e:
            logger.error(f"Failed to save window geometry: {e}")
        
        if self.queue_manager:
            try:
                self.queue_manager.stop()
            except Exception:
                pass
        
        if self.thread and self.thread.isRunning():
            if self.worker:
                self.worker.cancel()
            self.thread.quit()
            self.thread.wait(2000)
        
        event.accept()
