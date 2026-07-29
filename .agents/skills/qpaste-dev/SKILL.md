---
name: qpaste-dev
description: Development guide, execution commands, testing workflow, building procedures, and architecture reference for QPaste. Use when the user asks to run, test, build, debug, or understand QPaste.
---

# QPaste Development & Operational Skill

This skill provides reference commands, operational workflows, shortcut controls, and architectural layout for the QPaste project.

---

## 1. Environment & Execution Commands

### Running the App from Python Source
Run QPaste using the virtual environment interpreter:
```powershell
src\.venv\Scripts\python.exe src\main.py
```
*Note: QPaste runs silently in the Windows System Tray (Taskbar).*

### Running the Standalone Executable
```powershell
.\dist\qpaste.exe
```

### Killing Orphan / Stale QPaste Processes
If a process holds the Win32 Named Mutex during debugging:
```powershell
Get-Process python* -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*main.py*' -or $_.CommandLine -like '*qpaste*' } | Stop-Process -Force
```

---

## 2. Test Suite Execution

Run the complete 74-item unit and user story test suite:
```powershell
src\.venv\Scripts\python.exe -m pytest src/tests -v
```

Run a specific test module:
```powershell
src\.venv\Scripts\python.exe -m pytest src/tests/test_user_stories.py -v
```

---

## 3. Building & Packaging Releases

### Step 1: Build PyInstaller Executable
Compiles `src/main.py` into a single `--noconsole` binary in `dist/qpaste.exe`:
```powershell
src\.venv\Scripts\python.exe -m PyInstaller qpaste.spec
```

### Step 2: Build Inno Setup Installer
Compiles `installer/qpaste_setup.iss` into `QPaste_Setup_v1.0.0.exe`:
```powershell
iscc.exe installer/qpaste_setup.iss
```

---

## 4. Key Shortcut Controls

| Shortcut | Function | Description |
| :--- | :--- | :--- |
| **`F4`** | **Master Toggle** | Toggles Queue Mode `ON` or `OFF`. Displays Toast notification. |
| **`Shift + F4`** | **Clear Queue** | Empties all items in the FIFO queue and clears undo tracking. |
| **`Ctrl + C`** | **Sequential Copy** | When `ON`, appends copied text to the back of the FIFO queue. |
| **`Ctrl + V`** | **Sequential Paste** | When `ON`, pops oldest item (`popleft`) and pastes it. Falls back to OS paste if empty. |

---

## 5. Architecture & File Layout

```
qpaste/
├── src/
│   ├── main.py                  # App entry point, single-instance check, system tray
│   ├── core/
│   │   ├── clipboard_queue.py   # Thread-safe FIFO deque (max_size=25, push, pop, remove_at, move_item)
│   │   ├── listener.py          # Low-level pynput keyboard.Listener (WH_KEYBOARD_LL) & ShortcutHandler
│   │   ├── single_instance.py   # Win32 Named Mutex with atexit release
│   │   ├── state.py             # AppState manager for Master Toggle (ACTIVE vs PAUSED)
│   │   └── startup.py           # HKCU Registry auto-start manager
│   ├── ui/
│   │   ├── toast.py             # Win32 ToolWindow overlay (WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
│   │   └── inspector.py         # Tkinter dark-mode Visual Queue Inspector HUD
│   └── tests/                   # 74 passing pytest files
├── docs/
│   ├── PRD.md                   # Product Requirements Document
│   └── POC.md                   # Proof of Concept Verification Report
├── installer/
│   └── qpaste_setup.iss         # Inno Setup compilation script
└── qpaste.spec                  # PyInstaller build spec file
```
