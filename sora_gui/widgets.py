"""Custom widgets"""
from PySide6.QtWidgets import QFrame, QSizePolicy
from PySide6.QtCore import QSize
from PySide6.QtGui import QPainter, QColor, QPen, QFont

from .theme import THEME

class AspectPreview(QFrame):
    def __init__(self):
        super().__init__()
        self.size_str = "1280x720"
        self._aspect = (16, 9)
        self.setObjectName("AspectPreview")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(220)
        self._caption_font = QFont("Segoe UI", 10, QFont.Weight.DemiBold)
        self._text_font = QFont("Segoe UI", 12, QFont.Weight.Bold)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        aw, ah = self._aspect
        if aw <= 0 or ah <= 0:
            return self.minimumHeight()
        h = int(w * ah / aw)
        return max(h, self.minimumHeight())

    def sizeHint(self):
        w = 720
        return QSize(w, self.heightForWidth(w))

    def set_size_str(self, s):
        self.size_str = s
        parts = s.split("x")
        if len(parts) == 2:
            aw, ah = int(parts[0]), int(parts[1])
            gcd_val = self._gcd(aw, ah)
            self._aspect = (aw // gcd_val, ah // gcd_val)
        else:
            self._aspect = (16, 9)
        self.updateGeometry()
        self.update()
    
    def _gcd(self, a, b):
        while b:
            a, b = b, a % b
        return a

    def paintEvent(self, e):
        super().paintEvent(e)
        r = self.contentsRect().adjusted(12, 12, -12, -12)
        if r.width() <= 2 or r.height() <= 2:
            return
        
        parts = self.size_str.split("x")
        if len(parts) != 2:
            return
        aw, ah = int(parts[0]), int(parts[1])
        
        scale = min(r.width() / aw, r.height() / ah)
        rw = int(aw * scale)
        rh = int(ah * scale)
        x = r.x() + (r.width() - rw) // 2
        y = r.y() + (r.height() - rh) // 2

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        pen = QPen(QColor(THEME.primary_mid))
        pen.setWidth(3)
        p.setPen(pen)
        p.drawRect(x, y, rw, rh)

        p.setFont(self._text_font)
        p.setPen(QColor(THEME.text))
        text1 = self.size_str
        text1_width = p.fontMetrics().horizontalAdvance(text1)
        p.drawText(x + (rw - text1_width) // 2, y + rh // 2 - 10, text1)
        
        gcd_val = self._gcd(aw, ah)
        ar = f"{aw // gcd_val}:{ah // gcd_val}" if aw and ah else ""
        text2 = f"{aw}×{ah} • {ar}"
        
        p.setFont(self._caption_font)
        p.setPen(QColor(THEME.text_muted))
        text2_width = p.fontMetrics().horizontalAdvance(text2)
        p.drawText(x + (rw - text2_width) // 2, y + rh // 2 + 15, text2)
