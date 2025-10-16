"""Main application window"""
import os
from pathlib import Path

import requests
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QFormLayout, QHBoxLayout,
    QComboBox, QLineEdit, QTextEdit, QPushButton, QLabel, QFileDialog,
    QProgressBar, QPlainTextEdit, QMessageBox, QSplitter, QCheckBox, QSpinBox
)
from PySide6.QtCore import Qt, QSize, QThread, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication

try:
    from PIL import Image
except:
    Image = None

from .constants import API_BASE, SUPPORTED_SIZES, SUPPORTED_SECONDS
from .config import OUTPUT_DIR, get_saved_key, set_saved_key
from .utils import safe_json, pretty, aspect_of
from .widgets import AspectPreview
from .dialogs import JsonDialog
from .worker import Worker

class SoraApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sora Studio")
        self.setMinimumSize(QSize(1040, 820))
        self.last_response = None
        top = QWidget()
        top_layout = QVBoxLayout(top)
        form = QFormLayout()
        self.model_box = QComboBox()
        self.model_box.addItems(["sora-2", "sora-2-pro"])
        self.size_box = QComboBox()
        self.seconds_box = QComboBox()
        self.seconds_box.addItems(SUPPORTED_SECONDS)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("sk-...")
        self.save_key_btn = QPushButton("Save Key")
        self.test_key_btn = QPushButton("Test Key")
        key_row = QHBoxLayout()
        key_row.addWidget(self.api_key_edit, 1)
        key_row.addWidget(self.save_key_btn)
        key_row.addWidget(self.test_key_btn)
        self.preview = AspectPreview()
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("Insert your prompt here...")
        self.input_edit = QLineEdit()
        self.input_browse = QPushButton("Browse…")
        input_row = QHBoxLayout()
        input_row.addWidget(self.input_edit, 1)
        input_row.addWidget(self.input_browse)
        self.output_dir_edit = QLineEdit(str(OUTPUT_DIR))
        self.output_dir_btn = QPushButton("Change…")
        out_row = QHBoxLayout()
        out_row.addWidget(self.output_dir_edit, 1)
        out_row.addWidget(self.output_dir_btn)
        self.preflight_box = QCheckBox("Preflight moderation")
        self.preflight_box.setChecked(True)
        self.poll_spin = QSpinBox()
        self.poll_spin.setRange(1, 20)
        self.poll_spin.setValue(2)
        self.maxwait_spin = QSpinBox()
        self.maxwait_spin.setRange(1, 60)
        self.maxwait_spin.setValue(12)
        self.jobid_edit = QLineEdit()
        self.jobid_edit.setPlaceholderText("existing job id (optional)")
        self.resume_btn = QPushButton("Resume Job")
        self.copy_job_btn = QPushButton("Copy Job ID")
        poll_row = QHBoxLayout()
        poll_row.addWidget(QLabel("Poll every (s)"))
        poll_row.addWidget(self.poll_spin)
        poll_row.addWidget(QLabel("Max wait (min)"))
        poll_row.addWidget(self.maxwait_spin)
        poll_row.addStretch(1)
        jid_row = QHBoxLayout()
        jid_row.addWidget(self.jobid_edit, 1)
        jid_row.addWidget(self.resume_btn)
        jid_row.addWidget(self.copy_job_btn)
        self.send_btn = QPushButton("Generate")
        self.open_last_btn = QPushButton("Open Last File")
        self.open_last_btn.setEnabled(False)
        self.show_resp_btn = QPushButton("Show Last Response")
        self.show_resp_btn.setEnabled(False)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.send_btn)
        btn_row.addWidget(self.open_last_btn)
        btn_row.addWidget(self.show_resp_btn)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        form.addRow("Model", self.model_box)
        form.addRow("Size", self.size_box)
        form.addRow("Duration (s)", self.seconds_box)
        form.addRow("API Key", key_row)
        form.addRow("Aspect Preview", self.preview)
        form.addRow("Prompt", self.prompt_edit)
        form.addRow("Input Reference (optional)", input_row)
        form.addRow("Output Folder", out_row)
        form.addRow("Safety", self.preflight_box)
        form.addRow("Polling", poll_row)
        form.addRow("Job Control", jid_row)
        top_layout.addLayout(form)
        top_layout.addLayout(btn_row)
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.addWidget(self.progress)
        bottom_layout.addWidget(self.log, 1)
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(top)
        splitter.addWidget(bottom)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        cw = QWidget()
        cw_layout = QVBoxLayout(cw)
        cw_layout.addWidget(splitter)
        self.setCentralWidget(cw)
        self.model_box.currentTextChanged.connect(self.refresh_sizes)
        self.size_box.currentTextChanged.connect(self.on_size_change)
        self.input_browse.clicked.connect(self.browse_input)
        self.output_dir_btn.clicked.connect(self.browse_output)
        self.save_key_btn.clicked.connect(self.save_key)
        self.test_key_btn.clicked.connect(self.test_key)
        self.send_btn.clicked.connect(self.generate)
        self.show_resp_btn.clicked.connect(self.show_last_response)
        self.open_last_btn.clicked.connect(self.open_last_file)
        self.resume_btn.clicked.connect(self.resume_job)
        self.copy_job_btn.clicked.connect(self.copy_job_id)
        self.last_file = None
        self.thread = None
        self.worker = None
        self.api_key_edit.setText(get_saved_key())
        self.refresh_sizes()
        self.on_size_change(self.size_box.currentText())

    def refresh_sizes(self):
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

    def on_size_change(self, s):
        if s:
            self.preview.set_size_str(s)

    def browse_input(self):
        p, _ = QFileDialog.getOpenFileName(self, "Choose Image Reference", str(Path.home()), "Images (*.png *.jpg *.jpeg *.webp);;All Files (*)")
        if p:
            self.input_edit.setText(p)

    def browse_output(self):
        d = QFileDialog.getExistingDirectory(self, "Choose Output Folder", self.output_dir_edit.text())
        if d:
            self.output_dir_edit.setText(d)

    def save_key(self):
        k = self.api_key_edit.text().strip()
        if not k:
            QMessageBox.warning(self, "Missing", "Enter an API key first.")
            return
        set_saved_key(k)
        QMessageBox.information(self, "Saved", "API key saved.")

    def test_key(self):
        k = self.api_key_edit.text().strip()
        if not k:
            QMessageBox.warning(self, "Missing", "Enter an API key first.")
            return
        try:
            r = requests.get(f"{API_BASE}/models", headers={"Authorization": f"Bearer {k}"}, timeout=20)
            self.last_response = {"endpoint": "GET /models", "status": r.status_code, "body": safe_json(r)}
            self.show_resp_btn.setEnabled(True)
            if r.status_code == 200:
                QMessageBox.information(self, "OK", "Key looks valid.")
            else:
                QMessageBox.warning(self, "Error", f"{r.status_code}: {r.text[:400]}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def show_last_response(self):
        if self.last_response is None:
            QMessageBox.information(self, "Info", "No response captured yet.")
            return
        dlg = JsonDialog("Last API Response", self.last_response)
        dlg.exec()

    def run_moderation_check(self, api_key, prompt):
        try:
            r = requests.post(f"{API_BASE}/moderations", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json={"model": "omni-moderation-latest", "input": prompt}, timeout=60)
            self.last_response = {"endpoint": "POST /moderations", "status": r.status_code, "body": safe_json(r)}
            self.show_resp_btn.setEnabled(True)
            if r.status_code != 200:
                return True, ["moderation_request_failed"]
            body = r.json()
            res = body.get("results", [{}])[0]
            flagged = res.get("flagged", False)
            cats = res.get("categories", {}) or {}
            reasons = [k for k, v in cats.items() if v]
            return flagged, reasons
        except Exception:
            return True, ["moderation_request_failed"]

    def start_worker(self, job_id=None):
        k = self.api_key_edit.text().strip()
        m = self.model_box.currentText()
        size = self.size_box.currentText()
        sec = self.seconds_box.currentText()
        prompt = self.prompt_edit.toPlainText().strip()
        ref_path = self.input_edit.text().strip()
        out_dir = Path(self.output_dir_edit.text().strip() or str(OUTPUT_DIR))
        out_dir.mkdir(parents=True, exist_ok=True)
        self.progress.setValue(0)
        self.log.clear()
        self.send_btn.setEnabled(False)
        self.thread = QThread()
        self.worker = Worker(k, m, size, sec, prompt, ref_path, out_dir, job_id, self.poll_spin.value(), self.maxwait_spin.value())
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

    def generate(self):
        k = self.api_key_edit.text().strip()
        if not k:
            QMessageBox.warning(self, "Missing", "Enter and save your API key.")
            return
        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Missing", "Write a prompt.")
            return
        if self.preflight_box.isChecked():
            flagged, reasons = self.run_moderation_check(k, prompt)
            if flagged:
                QMessageBox.warning(self, "Blocked", f"Prompt flagged by moderation:\n{', '.join(reasons) or 'unspecified'}")
                return
        ref_path = self.input_edit.text().strip()
        size = self.size_box.currentText()
        if ref_path and Image:
            try:
                w, h = aspect_of(size)
                im = Image.open(ref_path)
                iw, ih = im.size
                if iw != w or ih != h:
                    if QMessageBox.question(self, "Resolution Mismatch", f"Image is {iw}x{ih}, target is {w}x{h}. Continue anyway?") != QMessageBox.Yes:
                        return
            except:
                pass
        self.start_worker(job_id=None)

    def resume_job(self):
        k = self.api_key_edit.text().strip()
        if not k:
            QMessageBox.warning(self, "Missing", "Enter and save your API key.")
            return
        jid = self.jobid_edit.text().strip()
        if not jid:
            QMessageBox.warning(self, "Missing", "Enter a job id to resume.")
            return
        self.start_worker(job_id=jid)

    def capture_last_response(self, payload):
        self.last_response = payload
        self.show_resp_btn.setEnabled(True)

    def on_saved(self, path):
        self.last_file = path
        self.open_last_btn.setEnabled(True)
        self.log.appendPlainText(f"Saved: {path}")

    def on_finished(self):
        self.send_btn.setEnabled(True)
        if self.thread:
            self.thread.quit()
            self.thread.wait()
            self.thread = None
            self.worker = None
        self.progress.setValue(100)

    def on_failed(self, msg):
        self.log.appendPlainText("Generation failed.")
        self.log.appendPlainText(str(msg))
        self.send_btn.setEnabled(True)
        if self.thread:
            self.thread.quit()
            self.thread.wait()
            self.thread = None
            self.worker = None

    def on_jobid(self, jid):
        self.jobid_edit.setText(jid)

    def open_last_file(self):
        if self.last_file and os.path.isfile(self.last_file):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_file))

    def copy_job_id(self):
        txt = self.jobid_edit.text().strip()
        if not txt:
            return
        QGuiApplication.clipboard().setText(txt)
