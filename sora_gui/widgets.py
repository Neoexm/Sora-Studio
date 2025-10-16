"""Custom widgets"""
from PySide6.QtWidgets import QFrame, QLabel
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QFont

from .utils import aspect_of

class AspectPreview(QFrame):
    def __init__(self):
        super().__init__()
        self.size_str = "1280x720"
        self.setStyleSheet("QFrame { background: #111; border: 1px solid #333; }")
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color: #ddd;")
        self.label.setText(self.size_str)
        self.label.setFont(QFont("Arial", 12, QFont.Bold))
        self._resize_to_aspect()

    def _resize_to_aspect(self):
        w, h = aspect_of(self.size_str)
        max_side = 360
        if w >= h:
            fw = max_side
            fh = int(max_side * h / w)
        else:
            fh = max_side
            fw = int(max_side * w / h)
        self.setFixedSize(QSize(fw + 24, fh + 24))
        self.update()

    def set_size_str(self, s):
        self.size_str = s
        self.label.setText(s)
        self._resize_to_aspect()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.label.setGeometry(self.rect())

    def paintEvent(self, e):
        super().paintEvent(e)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = aspect_of(self.size_str)
        box_w = self.width() - 24
        box_h = self.height() - 24
        r = min(box_w / w, box_h / h)
        rw = int(w * r)
        rh = int(h * r)
        x = (self.width() - rw) // 2
        y = (self.height() - rh) // 2
        pen = QPen(QColor("#66aaff"))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawRect(x, y, rw, rh)
