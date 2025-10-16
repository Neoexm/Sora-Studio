from math import gcd
from PySide6.QtCore import Qt, QSize, QRect
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy, QPushButton, QDialog

class AspectCanvas(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._w = 1280
        self._h = 720
        self._label = "1280x720"
        self._font = QFont("Segoe UI", 10, QFont.Weight.DemiBold)
        self.setObjectName("AspectPreview")
        self._mode = "mini"
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(160)

    def set_mode(self, mode):
        self._mode = mode
        if mode == "mini":
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.setFixedHeight(160)
        else:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.setMinimumHeight(320)
            self.setMaximumHeight(16777215)
        self.updateGeometry()
        self.update()

    def set_dimensions(self, w, h):
        w = max(1, int(w))
        h = max(1, int(h))
        self._w, self._h = w, h
        self._label = f"{w}x{h}"
        self.updateGeometry()
        self.update()

    def hasHeightForWidth(self):
        return self._mode != "mini"

    def heightForWidth(self, width):
        if self._mode == "mini":
            return self.height()
        width = max(1, int(width))
        return max(int(width * self._h / self._w), 320)

    def sizeHint(self):
        if self._mode == "mini":
            return QSize(480, 160)
        w = 960
        return QSize(w, self.heightForWidth(w))

    def _ratio_text(self):
        g = gcd(self._w, self._h)
        return f"{self._w//g}:{self._h//g}"

    def paintEvent(self, e):
        super().paintEvent(e)
        r = self.contentsRect().adjusted(12, 12, -12, -12)
        if r.width() <= 4 or r.height() <= 4:
            return
        scale = min(r.width() / self._w, r.height() / self._h)
        rw = int(self._w * scale)
        rh = int(self._h * scale)
        x = r.x() + (r.width() - rw) // 2
        y = r.y() + (r.height() - rh) // 2
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor("#66AAFF"))
        pen.setWidth(3)
        p.setPen(pen)
        p.drawRect(QRect(x, y, rw, rh))
        p.setFont(self._font)
        p.setPen(QColor("#E6EAF5"))
        p.drawText(x + rw - 160, y + 28, self._label)
        p.drawText(x + rw - 160, y + 50, f"{self._w}x{self._h} • {self._ratio_text()}")

class PreviewDialog(QDialog):
    def __init__(self, w, h, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aspect Preview")
        self.canvas = AspectCanvas(self)
        self.canvas.set_mode("dialog")
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas.set_dimensions(w, h)
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.addWidget(self.canvas, 1)
        self.resize(960, 640)

class CompactPreviewRow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.card = QFrame(self)
        self.card.setProperty("card", True)
        self.card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.canvas = AspectCanvas(self.card)
        self.canvas.set_mode("mini")
        self.canvas.setFixedHeight(160)
        self.title = QLabel("Aspect Preview", self.card)
        self.title.setProperty("heading", True)
        self.size_label = QLabel("1280×720 • 16:9", self.card)
        self.size_label.setProperty("muted", True)
        self.expand_btn = QPushButton("Expand", self.card)
        self.expand_btn.setProperty("variant", "primary")
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(6)
        left.addWidget(self.title, 0)
        left.addWidget(self.canvas, 0)
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(8)
        right.addWidget(self.size_label, 0)
        right.addStretch(1)
        right.addWidget(self.expand_btn, 0)
        row = QHBoxLayout(self.card)
        row.setContentsMargins(12, 12, 12, 12)
        row.setSpacing(12)
        row.addLayout(left, 1)
        row.addLayout(right, 0)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.card)
        self.expand_btn.clicked.connect(self._open_dialog)

    def set_dimensions(self, w, h):
        self.canvas.set_dimensions(w, h)
        g = gcd(max(1, w), max(1, h))
        self.size_label.setText(f"{w}×{h} • {w//g}:{h//g}")

    def _open_dialog(self):
        dlg = PreviewDialog(self.canvas._w, self.canvas._h, self)
        dlg.exec()
