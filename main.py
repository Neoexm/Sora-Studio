#!/usr/bin/env python3
"""Entry point for Sora 2 GUI application"""
import sys
from PySide6.QtWidgets import QApplication
from sora_gui.main_window import SoraApp

def main():
    app = QApplication(sys.argv)
    w = SoraApp()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
