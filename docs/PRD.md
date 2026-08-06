# Product Requirements Document (PRD): QPaste

> **Project Name:** QPaste  
> **Type:** Background Desktop Utility (Windows)  
> **Status:** Implementation & Expansion Phase  
> **Version:** 1.0.0  

---

## 1. Overview & Vision

**QPaste** is a lightweight, high-performance background utility for Windows designed for developers, researchers, and power users. Standard operating system clipboards only retain the single most recently copied item, forcing users to repeatedly switch windows back and forth when copying multiple snippets.

QPaste solves this by introducing a **Sequential FIFO (First-In, First-Out) Clipboard Manager**. Users can copy multiple text items sequentially using standard operating system shortcuts (`Ctrl+C`), and paste them in the exact chronological order they were collected (`Ctrl+V`).

It runs 100% silently in the Windows System Tray (Taskbar) without any window flashes on launch, providing native hotkey toggles, clean non-focus-stealing toast notifications, a visual Queue Inspector, and distribution options via both CLI portable binaries and GUI Setup installers.

---

## 2. Technology Stack & Distribution Architecture

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Language** | Python 3.11+ | Core application runtime & business logic |
| **System Tray** | `pystray` + `Pillow` | Native Windows taskbar icon and polished right-click menu |
| **Notifications** | `tkinter` + `ctypes` (Win32 API) | Native ToolWindow overlay (`WS_EX_TOOLWINDOW` + `WS_EX_NOACTIVATE`) with zero taskbar presence |
| **Keyboard Listener** | `pynput` | Global OS-level background hotkey interception (`Ctrl+V`, `F4`, `Shift+F4`) |
| **Clipboard Monitor** | `pyperclip` + `threading` | Background polling thread to capture OS clipboard changes without keystroke interception |
| **Clipboard API** | `pyperclip` | Cross-platform OS clipboard read/write interface |
| **Single-Instance Mutex** | `ctypes.windll.kernel32` / Win32 API | Prevents multiple instances of QPaste running simultaneously |
| **Auto-Start Engine** | `winreg` (Windows Registry) | Manages automatic launch on Windows boot via `HKCU\...\Run` |
| **GUI Queue Inspector** | `tkinter` (Native Dark Theme) | Minimal, lightweight window for viewing, deleting individual snippets, and clearing the queue |
| **CLI / Terminal Package** | `PyInstaller` | Bundles into single standalone `--noconsole` portable executable (`qpaste.exe`) |
| **Setup Installer** | Inno Setup | Packages full installer executable (`QPaste_Setup_v1.0.0.exe`) with Start Menu & Auto-Start integration |

---

## 3. Core User Flow & Shortcut Controls

### Key Controls & Triggers

1. **Master Toggle (`F4`)**:
   - Toggles **Queue Mode** `ON` or `OFF`.
   - Fires a clean dark charcoal Toast notification (`QPaste : ON` / `QPaste : OFF`) without stealing focus or flashing taskbar icons.
   - When **OFF**: Keyboard shortcuts pass through naturally; QPaste remains idle.
   - When **ON**: `Ctrl+V` is handled by QPaste's FIFO engine. OS clipboard changes are captured automatically.

2. **Clear Queue (`Shift + F4`)**:
   - Clears all items currently stored in the FIFO queue and fires a `QPaste : Cleared` toast notification.

3. **Polished System Tray Menu & Tray Icon Triggers**:
   - **Double-Click Tray Icon**: Opens the minimal Queue Inspector GUI window (`default=True`).
   - **Toggle Queue Mode (F4)**: Toggles Queue Mode ON/OFF.
   - **Clear Queue (Shift+F4)**: Empties the FIFO queue.
   - **Open Queue Inspector**: Opens the minimal GUI window to view, delete individual snippets, or clear the queue.
   - **Start with Windows**: Dynamically writes/removes registry keys to toggle silent launch on Windows boot.
   - **Exit**: Safely terminates the background service and unlocks single-instance mutex.

4. **Copy Action (Any OS Copy)**:
   - Captured automatically by a background clipboard monitor when Queue Mode is `ON`.
   - Safely reads newly copied text using a retry-loop to bypass "Access Denied" clipboard lock race conditions.
   - Appends text to the back of the FIFO queue and fires a fast (800ms) toast notification showing the new queue count.

5. **Paste Action (`Ctrl+V`)**:
   - Intercepted when Queue Mode is `ON`.
   - If Queue has items: Pops the oldest item (`pop(0)`), updates OS clipboard, and pastes it.
   - If Queue is empty: Falls back to normal OS clipboard behavior.

---

## 4. Detailed Functional Requirements

### 4.1 System Tray & Silent Launch Engine
- `REQ-1.1`: The app must launch 100% silently in the background, represented only by a System Tray icon without any console window or taskbar flashes on boot.
- `REQ-1.2`: Right-clicking the tray icon provides a polished menu for Queue Toggle, Queue Clear, Inspector launch, Windows startup configuration, and Exit.
- `REQ-1.3`: The app must automatically update its tray menu checkmark state when startup status changes.

### 4.2 Queue Management Engine
- `REQ-2.1`: Maintain a thread-safe list/deque of text strings.
- `REQ-2.4`: **Auto-Clear Queue Timer**:
  - Automatically expire and purge clipboard items after a user-specified duration (e.g., 30s, 1m, 5m, 15m, 30m, 1h).
  - Feature must be optional and toggleable (Enabled/Disabled).
  - Background expiration process must run safely without blocking UI or hotkey event threads.
  - Reset or handle timestamping for queue items so stale items are automatically removed upon timeout.
- `REQ-2.5`: **Persistent Settings**: Store auto-clear preferences (enabled status and timeout duration) persistently in a lightweight JSON configuration file (`config.json`).

### 4.3 Native Toast Overlay
- `REQ-3.1`: State notifications display at the bottom-right corner of the screen for 2 seconds (or 800ms for quick copy count badges).
- `REQ-3.2`: Must use `WS_EX_TOOLWINDOW` to guarantee zero presence on the Windows Taskbar or Alt+Tab switcher.
- `REQ-3.3`: Must use `WS_EX_NOACTIVATE` to prevent stealing window/keyboard focus from active applications.
- `REQ-3.4`: Uses a clean, minimal dark charcoal aesthetic with subtle dark borders.

### 4.4 Visual Queue Inspector (GUI HUD & Settings Interface)
- `REQ-4.1`: Accessible via System Tray right-click menu ("Open Queue Inspector") or by double-clicking the system tray icon.
- `REQ-4.2`: Displays live queued text items in a native GUI window matching the dark charcoal aesthetic.
- `REQ-4.3`: Minimal Functionality: Provides action buttons (`Delete` item, `Clear All` queue).
- `REQ-4.4`: Fast & Intuitive Interactions: Double-clicking an item in the list or pressing `Delete` deletes the selected snippet.
- `REQ-4.5`: Focuses non-disruptively; closing or hiding the window retains background QPaste clipboard monitoring.
- `REQ-4.6`: **Settings Tab / View**: Incorporate a dedicated **Settings** tab within the Queue Inspector GUI:
  - Toggle switch or checkbox for **Enable Auto-Clear Queue**.
  - Dropdown selector / entry field for **Auto-Clear Duration** (e.g., 30s, 1 minute, 5 minutes, 15 minutes, 30 minutes, 1 hour).
  - Immediate application and persistence of setting updates.

### 4.5 Windows Bootup Auto-Start Mechanism
- `REQ-5.1`: **Registry Autostart Key**: Manages entry under `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` with key name `QPaste`.
- `REQ-5.2`: **Executable Path Resolution**: Automatically detects whether running via raw `python main.py` or compiled `qpaste.exe` (using `sys.executable` or `sys.argv[0]`) to ensure valid path registration.
- `REQ-5.3`: **Installer Integration**: Inno Setup script adds a setup task checkbox *"Start QPaste automatically with Windows"* that writes the registry key on installation.

### 4.6 Single-Instance Mutex Enforcement
- `REQ-6.1`: On launch, QPaste attempts to create a Win32 Named Mutex `Local\QPaste_SingleInstance_Mutex`.
- `REQ-6.2`: If the mutex already exists (indicating an existing instance is active), the new process displays a Toast notification (*"QPaste is already running in System Tray"*) and exits immediately.
- `REQ-6.3`: Ensures zero duplicate keyboard hook conflicts or clipboard race conditions.

---

## 5. Distribution Specs & Packaging Architecture

### 5.1 PyInstaller Standalone Executable Packaging
- **Target File**: `dist/qpaste.exe`
- **Configuration**: `build_executable.py` / `qpaste.spec`
- **Build Flags**: `--noconsole --onefile --icon=assets/icon.ico --name=qpaste`
- **Asset Bundling**: Bundle `assets/icon.png` into PyInstaller runtime container. Use `sys._MEIPASS` fallback logic in resource loader.

### 5.2 Inno Setup Package (`QPaste_Setup_v1.0.0.exe`)
- **Script File**: `installer/qpaste_setup.iss`
- **Features**:
  - Installs binary to `{localappdata}\Programs\QPaste` (no UAC / Administrator prompt needed).
  - Creates Start Menu shortcut and optional Desktop shortcut.
  - Registers HKCU Run key if *"Start QPaste with Windows"* task is checked.
  - Clean uninstaller removing files, shortcut icons, and registry keys.

### 5.3 Source Control & Release Workflow
- **Git Tracking Scope**: Source files (`src/`), branding assets (`assets/`), build specs, and documentation are tracked in Git.
- **Ignored Build Output**: Build artifacts (`build/`), distribution binaries (`dist/`), and setup output (`installer/Output/`) are excluded via `.gitignore` to maintain lightweight commits (< 1 MB) and instantaneous `git push` syncs.
- **GitHub Release Publishing**: Executable releases (`qpaste.exe` and `QPaste_Setup_v1.0.0.exe`) are generated via PyInstaller and Inno Setup, then attached directly to tagged GitHub Releases.

---

## 6. Edge Cases & Handling Strategies

| Scenario | Risk | Mitigation Strategy |
| :--- | :--- | :--- |
| **Empty Queue on `Ctrl+V`** | App crash or lost paste | Passthrough to native OS clipboard paste |
| **Multiple App Launches** | Duplicate hook interception & race conditions | Acquire Win32 Named Mutex `Local\QPaste_SingleInstance_Mutex`; abort secondary process gracefully |
| **Clipboard Access Race Condition** | "Access Denied" error if an app locks the clipboard | Implement a 5-attempt retry loop with 50ms intervals in `pyperclip.paste()` |
| **Path Changes after Boot Startup** | Broken startup shortcut if exe moved | Registry path dynamically updated whenever "Start with Windows" is toggled from Tray |
| **Asset Path in PyInstaller Bundle** | Missing tray icon file crash | Use `getattr(sys, '_MEIPASS', os.path.dirname(__file__))` resolution helper |
| **Blocking pynput hooks** | Typing delay or `pynput` crash | Run all Toast Notifications and UI windows in detached daemon threads |

---
