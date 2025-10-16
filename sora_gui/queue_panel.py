from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QFrame
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
        self._setup_ui()
        
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._refresh_queue)
        self.update_timer.start(500)
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        card = QFrame(self)
        card.setProperty("card", True)
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(12)
        
        header = QHBoxLayout()
        header.setSpacing(12)
        
        title = QLabel("Queue", card)
        title.setProperty("heading", True)
        header.addWidget(title, 1)
        
        self.status_label = QLabel("0 queued, 0 active", card)
        self.status_label.setProperty("muted", True)
        header.addWidget(self.status_label)
        
        card_layout.addLayout(header)
        
        self.table = QTableWidget(card)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Prompt", "Model", "Size", "Duration", "Status", "Progress", "Actions"
        ])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        card_layout.addWidget(self.table, 1)
        
        footer = QHBoxLayout()
        footer.setSpacing(8)
        
        self.request_id_label = QLabel("Last Request ID:", card)
        self.request_id_label.setProperty("muted", True)
        footer.addWidget(self.request_id_label)
        
        self.request_id_text = QLabel("", card)
        footer.addWidget(self.request_id_text)
        
        self.copy_id_btn = QPushButton("Copy", card)
        self.copy_id_btn.clicked.connect(self._copy_request_id)
        footer.addWidget(self.copy_id_btn)
        
        footer.addStretch(1)
        
        card_layout.addLayout(footer)
        
        layout.addWidget(card)
    
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
        self.status_label.setText(
            f"{len(status['queued'])} queued, {len(status['active'])} active, "
            f"{len(status['completed'])} completed, {len(status['failed'])} failed"
        )
        
        self.table.setRowCount(0)
        
        with self.queue_manager.lock:
            row = 0
            for qs in self.queue_manager.queue:
                self._add_row(row, qs.shot.prompt[:50], qs.shot.model, 
                            f"{qs.shot.width}x{qs.shot.height}", 
                            f"{qs.shot.duration_s}s", qs.status_text, 
                            f"{qs.progress:.0%}", qs.shot.id)
                row += 1
            
            for shot_id, qs in self.queue_manager.active.items():
                self._add_row(row, qs.shot.prompt[:50], qs.shot.model,
                            f"{qs.shot.width}x{qs.shot.height}",
                            f"{qs.shot.duration_s}s", qs.status_text,
                            f"{qs.progress:.0%}", qs.shot.id)
                row += 1
    
    def _add_row(self, row: int, prompt: str, model: str, size: str, 
                 duration: str, status: str, progress: str, shot_id: str) -> None:
        self.table.insertRow(row)
        
        self.table.setItem(row, 0, QTableWidgetItem(prompt))
        self.table.setItem(row, 1, QTableWidgetItem(model))
        self.table.setItem(row, 2, QTableWidgetItem(size))
        self.table.setItem(row, 3, QTableWidgetItem(duration))
        self.table.setItem(row, 4, QTableWidgetItem(status))
        self.table.setItem(row, 5, QTableWidgetItem(progress))
        
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(4, 2, 4, 2)
        actions_layout.setSpacing(4)
        
        if row > 0:
            up_btn = QPushButton("↑")
            up_btn.setMaximumWidth(30)
            up_btn.clicked.connect(lambda: self._move_up(shot_id))
            actions_layout.addWidget(up_btn)
        
        down_btn = QPushButton("↓")
        down_btn.setMaximumWidth(30)
        down_btn.clicked.connect(lambda: self._move_down(shot_id))
        actions_layout.addWidget(down_btn)
        
        cancel_btn = QPushButton("✕")
        cancel_btn.setMaximumWidth(30)
        cancel_btn.clicked.connect(lambda: self._cancel_shot(shot_id))
        actions_layout.addWidget(cancel_btn)
        
        self.table.setCellWidget(row, 6, actions_widget)
    
    def _move_up(self, shot_id: str) -> None:
        if not self.queue_manager:
            return
        
        with self.queue_manager.lock:
            ids = [qs.shot.id for qs in self.queue_manager.queue]
            if shot_id in ids:
                idx = ids.index(shot_id)
                if idx > 0:
                    ids[idx], ids[idx-1] = ids[idx-1], ids[idx]
                    self.queue_manager.reorder(ids)
    
    def _move_down(self, shot_id: str) -> None:
        if not self.queue_manager:
            return
        
        with self.queue_manager.lock:
            ids = [qs.shot.id for qs in self.queue_manager.queue]
            if shot_id in ids:
                idx = ids.index(shot_id)
                if idx < len(ids) - 1:
                    ids[idx], ids[idx+1] = ids[idx+1], ids[idx]
                    self.queue_manager.reorder(ids)
    
    def _cancel_shot(self, shot_id: str) -> None:
        if not self.queue_manager:
            return
        
        self.queue_manager.cancel(shot_id)
    
    def _copy_request_id(self) -> None:
        if self.last_request_id:
            QGuiApplication.clipboard().setText(self.last_request_id)
