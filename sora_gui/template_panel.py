from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame,
    QLineEdit, QScrollArea, QMessageBox, QDialog, QFormLayout, QTextEdit,
    QComboBox, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QGuiApplication
from typing import Optional, List
import logging
import uuid

from sora_core.models import Template
from sora_gui.config import get_templates, save_templates

logger = logging.getLogger(__name__)

class TemplateDialog(QDialog):
    def __init__(self, template: Optional[Template] = None, parent=None):
        super().__init__(parent)
        self.template = template
        self.is_editing = template is not None
        self.setWindowTitle("Edit Template" if self.is_editing else "Create Template")
        self.setMinimumSize(500, 600)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(12)
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Template name")
        if self.is_editing:
            self.name_edit.setText(self.template.name)
        form.addRow("Name", self.name_edit)
        
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("Enter prompt template...")
        self.prompt_edit.setMinimumHeight(200)
        if self.is_editing:
            self.prompt_edit.setPlainText(self.template.prompt)
        form.addRow("Prompt", self.prompt_edit)
        
        self.model_box = QComboBox()
        self.model_box.addItems(["sora-2", "sora-2-pro"])
        if self.is_editing:
            idx = self.model_box.findText(self.template.model)
            if idx >= 0:
                self.model_box.setCurrentIndex(idx)
        form.addRow("Model", self.model_box)
        
        self.size_box = QComboBox()
        self.size_box.addItems([
            "1920x1080", "1280x720", "1080x1920", "720x1280",
            "1024x1792", "1792x1024", "1024x1024"
        ])
        if self.is_editing:
            size_str = f"{self.template.width}x{self.template.height}"
            idx = self.size_box.findText(size_str)
            if idx >= 0:
                self.size_box.setCurrentIndex(idx)
        form.addRow("Size", self.size_box)
        
        self.duration_box = QComboBox()
        self.duration_box.addItems(["5", "10", "12"])
        if self.is_editing:
            idx = self.duration_box.findText(str(self.template.duration_s))
            if idx >= 0:
                self.duration_box.setCurrentIndex(idx)
        form.addRow("Duration (s)", self.duration_box)
        
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("tag1, tag2, tag3")
        if self.is_editing and self.template.tags:
            self.tags_edit.setText(", ".join(self.template.tags))
        form.addRow("Tags", self.tags_edit)
        
        checkbox_row = QHBoxLayout()
        self.pinned_check = QCheckBox("Pinned")
        self.starred_check = QCheckBox("Starred")
        if self.is_editing:
            self.pinned_check.setChecked(self.template.pinned)
            self.starred_check.setChecked(self.template.starred)
        checkbox_row.addWidget(self.pinned_check)
        checkbox_row.addWidget(self.starred_check)
        checkbox_row.addStretch()
        form.addRow("", checkbox_row)
        
        layout.addLayout(form)
        
        buttons = QHBoxLayout()
        buttons.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save Template")
        save_btn.setProperty("variant", "primary")
        save_btn.clicked.connect(self._save)
        buttons.addWidget(save_btn)
        
        layout.addLayout(buttons)
    
    def _save(self):
        name = self.name_edit.text().strip()
        prompt = self.prompt_edit.toPlainText().strip()
        
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter a template name.")
            return
        
        if not prompt:
            QMessageBox.warning(self, "Missing Prompt", "Please enter a prompt template.")
            return
        
        size = self.size_box.currentText()
        w, h = map(int, size.split("x"))
        
        tags_text = self.tags_edit.text().strip()
        tags = [t.strip() for t in tags_text.split(",") if t.strip()] if tags_text else []
        
        if self.is_editing:
            self.template.name = name
            self.template.prompt = prompt
            self.template.model = self.model_box.currentText()
            self.template.width = w
            self.template.height = h
            self.template.duration_s = int(self.duration_box.currentText())
            self.template.tags = tags
            self.template.pinned = self.pinned_check.isChecked()
            self.template.starred = self.starred_check.isChecked()
        else:
            from datetime import datetime, timezone
            self.template = Template(
                id=str(uuid.uuid4()),
                name=name,
                prompt=prompt,
                model=self.model_box.currentText(),
                width=w,
                height=h,
                duration_s=int(self.duration_box.currentText()),
                tags=tags,
                pinned=self.pinned_check.isChecked(),
                starred=self.starred_check.isChecked(),
                created_at=datetime.now(timezone.utc).isoformat()
            )
        
        self.accept()
    
    def get_template(self) -> Template:
        return self.template


class TemplatePanel(QWidget):
    template_applied = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.templates: List[Template] = []
        self.filtered_templates: List[Template] = []
        self.expanded_items: set[str] = set()
        self.main_window = None
        self._setup_ui()
        self._load_templates()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        header = QHBoxLayout()
        header.setSpacing(8)
        
        title = QLabel("Templates")
        title.setProperty("heading", True)
        header.addWidget(title, 1)
        
        self.new_btn = QPushButton("+ New")
        self.new_btn.clicked.connect(self._create_template)
        header.addWidget(self.new_btn)
        
        layout.addLayout(header)
        
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search templates...")
        self.search_edit.textChanged.connect(self._filter_templates)
        search_row.addWidget(self.search_edit, 1)
        
        self.filter_pinned = QCheckBox("⭐ Pinned")
        self.filter_pinned.stateChanged.connect(self._filter_templates)
        search_row.addWidget(self.filter_pinned)
        
        self.filter_starred = QCheckBox("★ Starred")
        self.filter_starred.stateChanged.connect(self._filter_templates)
        search_row.addWidget(self.filter_starred)
        
        layout.addLayout(search_row)
        
        self.status_label = QLabel("0 templates")
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
    
    def set_templates(self, templates: List[Template]):
        self.templates = templates
        self._filter_templates()
    
    def _load_templates(self):
        """Load templates from global config"""
        templates_data = get_templates()
        self.templates = [Template(**t) for t in templates_data]
        self._filter_templates()
    
    def _save_templates(self):
        """Save templates to global config"""
        from dataclasses import asdict
        templates_data = [asdict(t) for t in self.templates]
        save_templates(templates_data)
    
    def _filter_templates(self):
        search_text = self.search_edit.text().strip().lower()
        show_pinned = self.filter_pinned.isChecked()
        show_starred = self.filter_starred.isChecked()
        
        self.filtered_templates = []
        for t in self.templates:
            if show_pinned and not t.pinned:
                continue
            if show_starred and not t.starred:
                continue
            
            if search_text:
                searchable = f"{t.name} {t.prompt} {' '.join(t.tags)}".lower()
                if search_text not in searchable:
                    continue
            
            self.filtered_templates.append(t)
        
        self.filtered_templates.sort(key=lambda t: (not t.pinned, not t.starred, t.name))
        
        self._refresh_templates()
    
    def _refresh_templates(self):
        while self.scroll_layout.count() > 1:
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        total = len(self.templates)
        shown = len(self.filtered_templates)
        
        if shown == total:
            self.status_label.setText(f"{total} template{'s' if total != 1 else ''}")
        else:
            self.status_label.setText(f"{shown}/{total} templates")
        
        for template in self.filtered_templates:
            item_widget = self._create_template_item(template)
            self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, item_widget)
    
    def _create_template_item(self, template: Template) -> QFrame:
        item = QFrame()
        item.setProperty("card", True)
        item.setObjectName(f"template_{template.id}")
        
        layout = QVBoxLayout(item)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        header = QWidget()
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.mousePressEvent = lambda e: self._toggle_expand(template.id, item)
        
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        
        icons = []
        if template.pinned:
            icons.append("⭐")
        if template.starred:
            icons.append("★")
        
        if icons:
            icon_label = QLabel(" ".join(icons))
            icon_label.setMinimumHeight(24)
            header_layout.addWidget(icon_label)
        
        name_label = QLabel(template.name)
        name_label.setStyleSheet("font-weight: 600; padding: 6px 0px;")
        name_label.setMinimumHeight(24)
        header_layout.addWidget(name_label, 1)
        
        if template.tags:
            tags_preview = ", ".join(template.tags[:3])
            if len(template.tags) > 3:
                tags_preview += "..."
            tags_label = QLabel(tags_preview)
            tags_label.setProperty("muted", True)
            tags_label.setMinimumHeight(24)
            header_layout.addWidget(tags_label)
        
        arrow_label = QLabel("▼ " if template.id in self.expanded_items else "▶ ")
        arrow_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        arrow_label.setMinimumHeight(24)
        header_layout.addWidget(arrow_label)
        
        layout.addWidget(header)
        
        if template.id in self.expanded_items:
            details = self._create_details_section(template)
            layout.addWidget(details)
        
        return item
    
    def _create_details_section(self, template: Template) -> QFrame:
        details = QFrame()
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(20, 10, 0, 0)
        details_layout.setSpacing(6)
        
        prompt_label = QLabel(f"Prompt:\n{template.prompt}")
        prompt_label.setWordWrap(True)
        prompt_label.setProperty("muted", True)
        prompt_label.setMinimumHeight(40)
        prompt_label.setStyleSheet("padding: 8px 0px;")
        details_layout.addWidget(prompt_label)
        
        model_label = QLabel(f"Model: {template.model}")
        model_label.setMinimumHeight(22)
        model_label.setStyleSheet("padding: 4px 0px;")
        details_layout.addWidget(model_label)
        
        size_label = QLabel(f"Size: {template.width}x{template.height}")
        size_label.setMinimumHeight(22)
        size_label.setStyleSheet("padding: 4px 0px;")
        details_layout.addWidget(size_label)
        
        duration_label = QLabel(f"Duration: {template.duration_s}s")
        duration_label.setMinimumHeight(22)
        duration_label.setStyleSheet("padding: 4px 0px;")
        details_layout.addWidget(duration_label)
        
        if template.tags:
            tags_label = QLabel(f"Tags: {', '.join(template.tags)}")
            tags_label.setMinimumHeight(22)
            tags_label.setStyleSheet("padding: 4px 0px;")
            details_layout.addWidget(tags_label)
        
        actions = QWidget()
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 8, 0, 0)
        actions_layout.setSpacing(6)
        
        apply_btn = QPushButton("Apply Template")
        apply_btn.setProperty("variant", "primary")
        apply_btn.setMinimumHeight(32)
        apply_btn.clicked.connect(lambda: self._apply_template(template))
        actions_layout.addWidget(apply_btn)
        
        edit_btn = QPushButton("Edit")
        edit_btn.setMinimumHeight(32)
        edit_btn.clicked.connect(lambda: self._edit_template(template))
        actions_layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("Delete")
        delete_btn.setMinimumHeight(32)
        delete_btn.clicked.connect(lambda: self._delete_template(template))
        actions_layout.addWidget(delete_btn)
        
        actions_layout.addStretch()
        details_layout.addWidget(actions)
        
        return details
    
    def _toggle_expand(self, template_id: str, item_widget: QFrame):
        if template_id in self.expanded_items:
            self.expanded_items.remove(template_id)
        else:
            self.expanded_items.add(template_id)
        self._refresh_templates()
    
    def _create_template(self):
        dlg = TemplateDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_template = dlg.get_template()
            self.templates.append(new_template)
            self._save_templates()
            self._filter_templates()
    
    def _edit_template(self, template: Template):
        dlg = TemplateDialog(template=template, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._save_templates()
            self._filter_templates()
    
    def _delete_template(self, template: Template):
        reply = QMessageBox.question(
            self,
            "Delete Template",
            f"Are you sure you want to delete '{template.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.templates.remove(template)
            if template.id in self.expanded_items:
                self.expanded_items.remove(template.id)
            self._save_templates()
            self._filter_templates()
    
    def _apply_template(self, template: Template):
        if self.main_window and hasattr(self.main_window, 'apply_template'):
            self.main_window.apply_template(template)
