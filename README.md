<div align="center">

<img src="assets/icon.png" alt="QPaste Logo" width="120" height="120" />

# QPaste

**Copy multiple things. Paste them in order. No Alt-Tab required.**

[![Windows](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?style=flat-square&logo=windows&logoColor=white)](https://github.com/chinthanasathyajithcs/qpaste)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/GUI-PyQt6-41CD52?style=flat-square&logo=qt&logoColor=white)](https://riverbankcomputing.com/software/pyqt/)
[![Release](https://img.shields.io/badge/Release-v1.0.0-2563EB?style=flat-square&logo=github&logoColor=white)](https://github.com/chinthanasathyajithcs/qpaste/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/chinthanasathyajithcs/qpaste/total?style=flat-square&logo=github&color=blue)](https://github.com/chinthanasathyajithcs/qpaste/releases)
[![Tests](https://img.shields.io/badge/Tests-78%20Passed-10B981?style=flat-square)](src/tests)
[![License](https://img.shields.io/badge/License-MIT-F59E0B?style=flat-square)](LICENSE)

[**Download Installer**](https://github.com/chinthanasathyajithcs/qpaste/releases/latest) &nbsp;·&nbsp; [**Download Portable**](https://github.com/chinthanasathyajithcs/qpaste/releases/latest) &nbsp;·&nbsp; [**Documentation**](docs/PRD.md)

<br />

![QPaste Demo](assets/Animation.gif)

</div>

---

## The Problem

Windows clipboard holds exactly one item. Copy something new and the previous item is gone. When you're filling out a form, migrating data between two apps, or batch-moving content from a spreadsheet, you end up in a maddening loop:

1. Switch to source. Copy field 1.
2. Switch to destination. Paste field 1.
3. Switch back to source. Copy field 2.
4. Switch back to destination. Paste field 2.
5. Repeat until you want to throw your monitor out the window.

## The Fix

QPaste adds a FIFO (First-In, First-Out) queue on top of your clipboard. You copy everything you need from the source first, then paste it all in order at the destination. No switching back and forth mid-task.

It runs as a system tray app. No window, no taskbar icon, no console. Press `F4` to arm it, copy your items, then paste them where you need them.

---

## How It Works

### FIFO Queue Flow

```
  COPY PHASE                        PASTE PHASE
  ──────────────────────────────    ─────────────────────────────
  Ctrl+C  "John Smith"          →   [ "John Smith" ]  ← front
  Ctrl+C  "john@example.com"    →   [ "John Smith", "john@example.com" ]
  Ctrl+C  "+1-555-0100"         →   [ "John Smith", "john@example.com", "+1-555-0100" ]

  Now switch to your destination app:

  Ctrl+V  →  pastes "John Smith"        queue: [ "john@example.com", "+1-555-0100" ]
  Ctrl+V  →  pastes "john@example.com"  queue: [ "+1-555-0100" ]
  Ctrl+V  →  pastes "+1-555-0100"       queue: [ ]

  Queue empty? Ctrl+V falls back to normal Windows paste. Nothing breaks.
```

### Queue Inspector

Press `F4` again at any time to see what's in the queue, remove individual items, or nuke everything:

```
  ┌─────────────────── QPaste Inspector ───────────────────────┐
  │                                                             │
  │  [1]  John Smith                                    [x]    │
  │  [2]  john@example.com                              [x]    │
  │  [3]  +1-555-0100                                   [x]    │
  │                                                             │
  │  [ Clear All ]                    Status: ACTIVE (3 items) │
  └─────────────────────────────────────────────────────────────┘
```

### Quick Notepad HUD

`F3` pops a floating dark scratchpad over whatever window you're in. It's frameless, draggable, and persists your text across sessions. Good for stashing snippets, keeping a reference visible while you work, or just temporary scratch space.

```
  ┌────────────────── Quick Notepad ─── [x] ─┐
  │                                           │
  │  meeting notes:                           │
  │  - ask about timeline                     │
  │  - confirm budget sign-off                │
  │  - follow up re: staging env              │
  │                                           │
  └───────────────────────────────────────────┘
        Draggable. Auto-saves. Always on top.
```

---

## Hotkeys

| Key | Action | Customizable |
|-----|--------|:---:|
| `F4` | Toggle queue mode ON / OFF | Yes |
| `Shift+F4` | Clear all queued items | Yes |
| `F3` | Toggle Quick Notepad HUD | Yes |
| `Ctrl+C` | Copy to queue (when active) | No |
| `Ctrl+V` | Paste from queue front (falls back to standard paste when empty/OFF) | No |

To change the `F3`, `F4`, or `Shift+F4` bindings: open the Queue Inspector, go to the **Settings** tab, and type any key or combo into the hotkey fields. Changes apply immediately without a restart.

---

## Why It Feels Solid

### Office / Word Multi-Copy Debounce

When you copy something in Microsoft Word or Excel, those apps fire multiple clipboard change events in rapid succession. Each copy action sends the same text in several formats (plain text, RTF, HTML, OLE) within milliseconds of each other. Without debouncing, your queue would fill up with 3-4 duplicates from a single `Ctrl+C`.

QPaste waits 200ms after the first clipboard event before accepting the copy. It also deduplicates identical content copied within a 1-second window. You get exactly one clean item per copy action, regardless of what Office does behind the scenes. Both thresholds are configurable in the Inspector's Settings tab.

### Activity-Based Idle Auto-Clear

The queue doesn't expire on a fixed timer. It uses idle-mode auto-clear: the timer resets every time you copy something, so an active work session keeps your items alive indefinitely. The queue only clears after you've been genuinely idle for the configured timeout (default: 60 seconds, configurable from 30s to 1 hour).

This means copying 20 items across a long task works fine. You won't come back from a quick Slack check to find your queue gone mid-paste.

---

## Getting Started

### Prerequisites

- Windows 10 or 11
- Python 3.10+

### Quickstart

```powershell
# Clone and enter the repo
git clone https://github.com/chinthanasathyajithcs/qpaste.git
cd qpaste

# Create and activate a virtual environment
python -m venv src\.venv
.\src\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r src\requirements.txt

# Run it
python src\main.py
```

QPaste starts silently in your system tray. Right-click the tray icon for controls, or use the hotkeys immediately.

### Running Tests

```powershell
python3 -m unittest discover -s src/tests
```

78 tests covering queue logic, hotkey parsing, debounce behavior, notepad persistence, and UI integration.

### Building a Standalone Executable

```powershell
# Produces dist/qpaste.exe
python -m PyInstaller qpaste.spec
```

For the full Windows installer (requires [Inno Setup 6](https://jrsoftware.org/isinfo.php)):

```powershell
ISCC.exe installer\qpaste_setup.iss
```

---

## Project Structure

```
qpaste/
├── assets/                  # App icon and demo GIF
├── docs/                    # Product Requirements Document
├── installer/               # Inno Setup script and installer output
├── src/
│   ├── core/
│   │   ├── clipboard_queue.py   # Thread-safe FIFO queue (up to 25 items)
│   │   ├── config.py            # Persistent JSON settings manager
│   │   ├── hotkey_parser.py     # Hotkey string parsing and validation
│   │   ├── listener.py          # Keyboard hooks, clipboard listener, debounce
│   │   ├── single_instance.py   # Win32 Named Mutex (prevents duplicate processes)
│   │   ├── startup.py           # Windows registry autostart manager
│   │   └── state.py             # Active/inactive state manager
│   ├── ui/
│   │   ├── inspector.py         # Queue Inspector window
│   │   ├── notepad.py           # Quick Notepad HUD overlay
│   │   ├── settings_tab.py      # Hotkey and config settings UI
│   │   └── toast.py             # Focus-stealing-free toast notification
│   ├── tests/                   # 78 automated unit and integration tests
│   └── main.py                  # Entry point
└── qpaste.spec              # PyInstaller build spec
```

---

## License

[MIT License](LICENSE) © 2026 ChinthanaSathyajith.

---

<div align="center">
  <sub>If QPaste saved you from tab-switching hell, a ⭐ <b>Star</b> goes a long way.</sub>
</div>
