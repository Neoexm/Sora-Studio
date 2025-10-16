"""Dialogs"""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QPlainTextEdit, QDialogButtonBox

from .utils import pretty

class JsonDialog(QDialog):
    def __init__(self, title, payload):
        super().__init__()
        self.setWindowTitle(title)
        self.setMinimumSize(600, 500)
        v = QVBoxLayout(self)
        txt = QPlainTextEdit(self)
        txt.setReadOnly(True)
        txt.setPlainText(pretty(payload))
        v.addWidget(txt)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        bb.accepted.connect(self.accept)
        v.addWidget(bb)
