# Sora Studio

<p align="center">
  <img alt="Sora Studio" src="./logo.svg" width="560">
</p>

<p align="center">
  <a href="https://github.com/Neoexm/Sora-Studio/releases">
    <img alt="Release" src="https://img.shields.io/github/v/release/Neoexm/Sora-Studio?sort=semver">
  </a>
  <a href="https://github.com/Neoexm/Sora-Studio/actions">
    <img alt="Build" src="https://img.shields.io/github/actions/workflow/status/Neoexm/Sora-Studio/ci.yml?branch=main">
  </a>
  <a href="https://github.com/Neoexm/Sora-Studio/blob/main/LICENSE">
    <img alt="License" src="https://img.shields.io/github/license/Neoexm/Sora-Studio">
  </a>
  <img alt="Commit Activity" src="https://img.shields.io/github/commit-activity/m/Neoexm/Sora-Studio">
  <a href="https://github.com/Neoexm/Sora-Studio/issues">
    <img alt="Issues" src="https://img.shields.io/github/issues/Neoexm/Sora-Studio">
  </a>
  <img alt="Downloads" src="https://img.shields.io/github/downloads/Neoexm/Sora-Studio/total">
</p>

Sleek desktop GUI for AI video generation with Sora 2 / Sora 2 Pro — prompt-to-video, live aspect preview, reference images, resumable jobs.

---

## Features
- Sora 2 / Sora 2 Pro selection, duration and size presets with live aspect preview  
- Reference image upload with resolution checks  
- Moderation preflight (toggleable)  
- Detailed progress and raw API response viewer with request IDs  
- Resumable by Job ID, robust polling with retries and 99% “stuck” recovery  
- Output folder chooser and one-click open  

## Quickstart

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
````

On first run, paste your API key and click **Save Key**. Keys are stored in Windows Credential Manager, with a config-file fallback at `%USERPROFILE%\.sora2gui`.

## Build a Windows EXE

```powershell
pyinstaller main.py `
  --name SoraStudio `
  --onefile `
  --windowed `
  --clean `
  --collect-all PySide6 `
  --collect-all keyring `
  --collect-all platformdirs `
  --collect-all sora_gui `
  --icon .\icon.ico
```

The executable will be at `dist\SoraStudio.exe`.

## Troubleshooting

* `moderation_blocked`: rewrite the prompt to avoid openai's overly strict content policys
* Poll `500` or stuck at `99%`: the app auto-retries and attempts a download even if status is `failed`. Use **Resume Job** with the same ID if needed. Include request IDs from **Show Last Response** when filing issues.