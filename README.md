<div align="center">

<img src="assets/icon.png" alt="QPaste Logo" width="120" height="120" />

# QPaste

**Copy continuously. Paste sequentially. Zero tab-switching required.**

[![Windows](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?style=flat-square&logo=windows&logoColor=white)](https://github.com/chinthanasathyajithcs/qpaste)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/GUI-PyQt6-41CD52?style=flat-square&logo=qt&logoColor=white)](https://riverbankcomputing.com/software/pyqt/)
[![Release](https://img.shields.io/badge/Release-v1.0.0-2563EB?style=flat-square&logo=github&logoColor=white)](https://github.com/chinthanasathyajithcs/qpaste/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/chinthanasathyajithcs/qpaste/total?style=flat-square&logo=github&color=blue)](https://github.com/chinthanasathyajithcs/qpaste/releases)
[![Tests](https://img.shields.io/badge/Tests-78%20Passed-10B981?style=flat-square)](src/tests)
[![License](https://img.shields.io/badge/License-MIT-F59E0B?style=flat-square)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=flat-square)](https://github.com/chinthanasathyajithcs/qpaste)

[**Download Installer**](https://github.com/chinthanasathyajithcs/qpaste/releases/latest) &nbsp;·&nbsp; [**Download Portable**](https://github.com/chinthanasathyajithcs/qpaste/releases/latest) &nbsp;·&nbsp; [**Documentation**](docs/PRD.md)

<br />

![QPaste Demo](assets/Animation.gif)

</div>

---

## 📖 Overview

### The Problem
The standard Windows clipboard holds only a single item at a time. Copying a new snippet immediately overwrites the previous one. When collecting multiple pieces of text across documents or web pages, you have to constantly switch back and forth between windows to copy and paste each item individually.

### The Solution
**QPaste** adds a First-In, First-Out (FIFO) queue on top of your clipboard. When Queue Mode is active:

- **Copy Phase**: Copy multiple items in sequence (`Ctrl+C`). Each item is added to the back of the queue.
- **Paste Phase**: Paste items in the exact order they were copied (`Ctrl+V`). Each paste retrieves the oldest item from the queue.

When the queue is empty, `Ctrl+V` reverts to standard Windows paste behavior. QPaste runs quietly in your System Tray without console windows or taskbar icons.

---

## ⚡ Features

- **Sequential FIFO Queue**: Thread-safe queue supporting up to 25 items in memory.
- **System Tray Execution**: Runs in the background with a tray icon and context menu for controls.
- **Non-Intrusive Overlay**: Brief floating toast notification displays status (`QPaste : ON` / `OFF`) and queue counts without stealing window focus.
- **Queue Inspector GUI**: Minimal dark-themed window to view queued snippets, remove individual items, or clear the queue.
- **Auto-Clear Expiration**: Configurable timer (30s to 1 hour) to automatically purge stale items from memory.
- **Start with Windows**: Toggleable registry integration for silent startup on boot.
- **Single Instance Enforcement**: Win32 Named Mutex prevents duplicate background processes and hotkey conflicts.
- **Clipboard Lock Protection**: Automatic 5-attempt retry handler for transient Windows clipboard locks.

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `F4` | Toggle Queue Mode ON / OFF |
| `Shift + F4` | Clear all queued items |
| `Ctrl + C` | Copy text (queued sequentially when active) |
| `Ctrl + V` | Paste next item from queue (standard paste when empty/OFF) |

---

## 📥 Installation

### Direct Downloads

- **[QPaste_Setup_v1.0.0.exe](https://github.com/chinthanasathyajithcs/qpaste/releases/latest)** — Standard Windows installer. Installs to `%LocalAppData%\Programs\QPaste`, adds Start Menu shortcuts, autostart option, and uninstaller.
- **[qpaste.exe](https://github.com/chinthanasathyajithcs/qpaste/releases/latest)** — Standalone portable executable. No installation required.

### Package Managers

```powershell
# Windows Package Manager (winget)
winget install QPaste

# Scoop
scoop bucket add qpaste https://github.com/chinthanasathyajithcs/qpaste
scoop install qpaste

# Chocolatey
choco install qpaste
```

---

## 🛠️ Development

### Prerequisites
- Python 3.11+
- Windows 10 / 11
- PyInstaller (for building executable)
- Inno Setup 6 (for building installer)

### Setup & Execution

```powershell
# Clone repository
git clone https://github.com/chinthanasathyajithcs/qpaste.git
cd qpaste

# Create and activate virtual environment
python -m venv src\.venv
.\src\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r src\requirements.txt

# Run application
python src\main.py

# Run test suite
pytest
```

### Building Binaries

```powershell
# Standalone executable -> dist/qpaste.exe
python -m PyInstaller qpaste.spec

# Setup installer -> installer/Output/QPaste_Setup_v1.0.0.exe
ISCC.exe installer\qpaste_setup.iss
```

---

## 📁 Project Structure

```
qpaste/
├── assets/                  # App icon assets & demo animation GIF
├── docs/                    # Product Requirements Document
├── installer/               # Inno Setup compilation script & installer output
├── src/
│   ├── core/
│   │   ├── clipboard_queue.py   # Thread-safe FIFO queue implementation
│   │   ├── config.py            # Persistent JSON settings manager
│   │   ├── listener.py          # Keyboard hooks & Win32 clipboard listener
│   │   ├── single_instance.py   # Win32 Named Mutex enforcement
│   │   ├── startup.py           # Windows registry autostart manager
│   │   └── state.py             # Active state manager
│   ├── ui/
│   │   ├── inspector.py         # Queue Inspector GUI & Settings tab
│   │   └── toast.py             # Focusless toast overlay
│   ├── tests/                   # 78 automated unit and integration tests
│   └── main.py                  # Process entry point
└── qpaste.spec              # PyInstaller build spec
```

---

## 📄 License

[MIT License](LICENSE) © 2026 ChinthanaSathyajith.

---

<div align="center">
  <sub>If QPaste saved you tab-switching time, don't forget to leave a ⭐ <b>Star</b> at the top right!</sub>
</div>
