from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame,
    QListWidget, QListWidgetItem, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QGuiApplication
from typing import Optional
import logging

from sora_core.queue import QueueManager

logger = logging.getLogger(__name__)

class QueuePanel(QWidget):
    shot_selected = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.queue_manager: Optional[QueueManager] = None
        self.last_request_id: str = ""
        self.expanded_items: set[str] = set()
        self._last_item_count: int = 0
        self._setup_ui()
        
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._refresh_queue)
        self.update_timer.start(500)
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        header = QHBoxLayout()
        header.setSpacing(8)
        
        title = QLabel("Queue")
        title.setProperty("heading", True)
        header.addWidget(title, 1)
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self._clear_completed)
        header.addWidget(self.clear_btn)
        
        layout.addLayout(header)
        
        self.status_label = QLabel("0 items")
        self.status_label.setProperty("muted", True)
        layout.addWidget(self.status_label)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(8)
        self.scroll_layout.addStretch()
        
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area, 1)
        
        footer = QFrame()
        footer.setProperty("card", True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(8, 6, 8, 6)
        footer_layout.setSpacing(6)
        
        footer_layout.addWidget(QLabel("Last ID:"))
        self.request_id_text = QLabel("")
        self.request_id_text.setProperty("muted", True)
        footer_layout.addWidget(self.request_id_text, 1)
        
        self.copy_id_btn = QPushButton("Copy")
        self.copy_id_btn.clicked.connect(self._copy_request_id)
        footer_layout.addWidget(self.copy_id_btn)
        
        layout.addWidget(footer)
    
    def set_queue_manager(self, qm: QueueManager) -> None:
        self.queue_manager = qm
        self._refresh_queue()
    
    def set_last_request_id(self, request_id: str) -> None:
        self.last_request_id = request_id
        self.request_id_text.setText(request_id)
    
    def _refresh_queue(self) -> None:
        if not self.queue_manager:
            return
        
        status = self.queue_manager.get_queue_status()
        total = len(status['queued']) + len(status['active'])
        self.status_label.setText(
            f"{total} items • {len(status['active'])} active"
        )
        
        items = self.queue_manager.get_all_items()
        
        current_items = {}
        for i in range(self.scroll_layout.count() - 1):
            widget = self.scroll_layout.itemAt(i).widget()
            if widget and widget.objectName().startswith("queue_item_"):
                shot_id = widget.objectName().replace("queue_item_", "")
                current_items[shot_id] = widget
        
        new_shot_ids = {shot_id for shot_id, _, _, _ in items}
        
        for shot_id in list(current_items.keys()):
            if shot_id not in new_shot_ids:
                current_items[shot_id].deleteLater()
                del current_items[shot_id]
        
        for idx, (shot_id, shot, priority, status_text) in enumerate(items):
            if shot_id not in current_items:
                item_widget = self._create_queue_item(shot_id, shot, status_text)
                self.scroll_layout.insertWidget(idx, item_widget)
            else:
                existing = current_items[shot_id]
                self._update_queue_item(existing, shot_id, shot, status_text)
                current_idx = self.scroll_layout.indexOf(existing)
                if current_idx != idx:
                    self.scroll_layout.removeWidget(existing)
                    self.scroll_layout.insertWidget(idx, existing)
    
    def _update_queue_item(self, item: QFrame, shot_id: str, shot, status_text: str) -> None:
        """Update an existing queue item widget"""
        layout = item.layout()
        if not layout:
            return
        
        is_expanded = shot_id in self.expanded_items
        
        if is_expanded and layout.count() == 1:
            details = self._create_details_section(shot_id, shot, status_text)
            layout.addWidget(details)
        elif not is_expanded and layout.count() > 1:
            details_widget = layout.itemAt(1).widget()
            if details_widget:
                layout.removeWidget(details_widget)
                details_widget.deleteLater()
    
    def _create_queue_item(self, shot_id: str, shot, status_text: str) -> QFrame:
        item = QFrame()
        item.setProperty("card", True)
        item.setObjectName(f"queue_item_{shot_id}")
        item.setMinimumHeight(50)
        
        layout = QVBoxLayout(item)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        header = QWidget()
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.setAttribute(Qt.WidgetAttribute.WA_Hover, False)
        header.mousePressEvent = lambda e: self._toggle_expand(shot_id, item)
        
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)
        
        status_emoji = {
            "queued": "⏳",
            "processing": "⚙️",
            "active": "⚙️",
            "completed": "✅",
            "failed": "❌",
            "cancelled": "🚫"
        }.get(status_text, "⏳")
        
        status_label = QLabel(status_emoji)
        status_label.setMinimumHeight(24)
        header_layout.addWidget(status_label)
        
        resume_job_id = getattr(shot, 'job_id', None)
        if resume_job_id:
            resume_icon = QLabel("🔄")
            resume_icon.setToolTip(f"Resume job: {resume_job_id}")
            resume_icon.setMinimumHeight(24)
            header_layout.addWidget(resume_icon)
        
        prompt = shot.prompt[:60] + "..." if len(shot.prompt) > 60 else shot.prompt
        prompt_label = QLabel(prompt)
        prompt_label.setWordWrap(True)
        prompt_label.setMinimumHeight(24)
        prompt_label.setStyleSheet("padding: 6px 0px;")
        header_layout.addWidget(prompt_label, 1)
        
        arrow_label = QLabel("▼ " if shot_id in self.expanded_items else "▶ ")
        arrow_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        arrow_label.setMinimumHeight(24)
        header_layout.addWidget(arrow_label)
        
        layout.addWidget(header)
        
        if shot_id in self.expanded_items:
            details = self._create_details_section(shot_id, shot, status_text)
            layout.addWidget(details)
        
        return item
    
    def _create_details_section(self, shot_id: str, shot, status_text: str) -> QFrame:
        """Create expanded details section"""
        details = QFrame()
        details.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(20, 10, 0, 0)
        details_layout.setSpacing(6)
        
        resume_job_id = getattr(shot, 'job_id', None)
        if resume_job_id:
            resume_label = QLabel(f"🔄 Resume Job ID: {resume_job_id}")
            resume_label.setMinimumHeight(22)
            resume_label.setStyleSheet("padding: 4px 0px; color: #4a9eff; font-weight: bold;")
            details_layout.addWidget(resume_label)
        
        model_label = QLabel(f"Model: {shot.model}")
        model_label.setMinimumHeight(22)
        model_label.setStyleSheet("padding: 4px 0px;")
        details_layout.addWidget(model_label)
        
        size_label = QLabel(f"Size: {shot.width}x{shot.height}")
        size_label.setMinimumHeight(22)
        size_label.setStyleSheet("padding: 4px 0px;")
        details_layout.addWidget(size_label)
        
        duration_label = QLabel(f"Duration: {shot.duration_s}s")
        duration_label.setMinimumHeight(22)
        duration_label.setStyleSheet("padding: 4px 0px;")
        details_layout.addWidget(duration_label)
        
        status_label = QLabel(f"Status: {status_text}")
        status_label.setMinimumHeight(22)
        status_label.setStyleSheet("padding: 4px 0px;")
        details_layout.addWidget(status_label)
        
        prompt_detail = QLabel(f"Prompt:\n{shot.prompt}")
        prompt_detail.setWordWrap(True)
        prompt_detail.setProperty("muted", True)
        prompt_detail.setMinimumHeight(70)
        prompt_detail.setStyleSheet("padding: 8px 0px;")
        details_layout.addWidget(prompt_detail)
        
        actions = QWidget()
        actions.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        actions.setMouseTracking(True)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 8, 0, 0)
        actions_layout.setSpacing(6)
        
        if status_text in ("queued", "processing", "active"):
            cancel_btn = QPushButton("✕ Cancel")
            cancel_btn.setMinimumHeight(32)
            cancel_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            cancel_btn.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
            def cancel_click(sid=shot_id):
                self._cancel_shot(sid)
            cancel_btn.clicked.connect(cancel_click)
            actions_layout.addWidget(cancel_btn)
        
        up_btn = QPushButton("↑")
        up_btn.setMaximumWidth(36)
        up_btn.setMinimumHeight(32)
        up_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        up_btn.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        def up_click(sid=shot_id):
            self._move_up(sid)
        up_btn.clicked.connect(up_click)
        actions_layout.addWidget(up_btn)
        
        down_btn = QPushButton("↓")
        down_btn.setMaximumWidth(36)
        down_btn.setMinimumHeight(32)
        down_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        down_btn.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        def down_click(sid=shot_id):
            self._move_down(sid)
        down_btn.clicked.connect(down_click)
        actions_layout.addWidget(down_btn)
        
        if status_text == "completed":
            output_file = getattr(shot, 'output_path', None)
            logger.info(f"Queue item {shot_id}: status={status_text}, output_path={output_file}, type={type(output_file)}")
            if output_file and isinstance(output_file, str) and output_file != "":
                open_btn = QPushButton("📁 Open Video")
                open_btn.setMinimumHeight(32)
                open_btn.setStyleSheet("QPushButton { background: #2d5016; }")
                
                actual_path = str(output_file)
                
                def open_video():
                    from PySide6.QtCore import QUrl
                    from PySide6.QtGui import QDesktopServices
                    import os
                    logger.info(f"Opening video: {actual_path}, exists={os.path.exists(actual_path)}")
                    if os.path.exists(actual_path):
                        QDesktopServices.openUrl(QUrl.fromLocalFile(actual_path))
                    else:
                        logger.warning(f"Video file not found: {actual_path}")
                
                open_btn.clicked.connect(open_video)
                actions_layout.addWidget(open_btn)
        
        actions_layout.addStretch()
        details_layout.addWidget(actions)
        
        return details
    
    def _toggle_expand(self, shot_id: str, item_widget: QFrame) -> None:
        if shot_id in self.expanded_items:
            self.expanded_items.remove(shot_id)
        else:
            self.expanded_items.add(shot_id)
        self._refresh_queue()
    
    def _move_up(self, shot_id: str) -> None:
        if not self.queue_manager:
            return
        
        items = self.queue_manager.get_all_items()
        ids = [sid for sid, _, _, _ in items]
        if shot_id in ids:
            idx = ids.index(shot_id)
            if idx > 0:
                ids[idx], ids[idx-1] = ids[idx-1], ids[idx]
                self.queue_manager.reorder(ids)
    
    def _move_down(self, shot_id: str) -> None:
        if not self.queue_manager:
            return
        
        items = self.queue_manager.get_all_items()
        ids = [sid for sid, _, _, _ in items]
        if shot_id in ids:
            idx = ids.index(shot_id)
            if idx < len(ids) - 1:
                ids[idx], ids[idx+1] = ids[idx+1], ids[idx]
                self.queue_manager.reorder(ids)
    
    def _cancel_shot(self, shot_id: str) -> None:
        if not self.queue_manager:
            return
        
        self.queue_manager.cancel(shot_id)
        self._refresh_queue()
    
    def _clear_completed(self) -> None:
        if not self.queue_manager:
            return
        
        self.queue_manager.clear_completed()
        self._refresh_queue()
    
    def _copy_request_id(self) -> None:
        if self.last_request_id:
            QGuiApplication.clipboard().setText(self.last_request_id)
