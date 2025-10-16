#!/usr/bin/env python3
"""Entry point for Sora 2 GUI application"""
import sys
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication
from sora_gui.main_window import SoraApp
from sora_gui.config import CONFIG_DIR

def setup_logging():
    """Setup application logging"""
    log_dir = CONFIG_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "sora_studio.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Starting Sora Studio")
    logger.info(f"Log file: {log_file}")

def main():
    """Main application entry point"""
    setup_logging()
    app = QApplication(sys.argv)
    w = SoraApp()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
