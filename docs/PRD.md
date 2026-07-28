# Product Requirements Document (PRD): QPaste

> **Project Name:** QPaste  
> **Type:** Background Desktop Utility (Windows)  
> **Status:** Implementation Phase  
> **Version:** 1.0.0  

---

## 1. Overview & Vision

**QPaste** is a lightweight, high-performance background utility for Windows designed for developers, researchers, and power users. Standard operating system clipboards only retain the single most recently copied item, forcing users to repeatedly switch windows back and forth when copying multiple snippets.

QPaste solves this by introducing a **Sequential FIFO (First-In, First-Out) Clipboard Manager**. Users can copy multiple text items sequentially using standard operating system shortcuts (`Ctrl+C`), and paste them in the exact chronological order they were collected (`Ctrl+V`).

It runs 100% silently in the Windows System Tray (Taskbar) without any window flashes on launch, while providing native hotkey toggles and clean, non-focus-stealing toast notifications.

---

## 2. Technology Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Language** | Python 3.11+ | Core application runtime & business logic |
| **System Tray** | `pystray` + `Pillow` | Native Windows taskbar icon and right-click menu |
| **Notifications** | `tkinter` + `ctypes` (Win32 API) | Native ToolWindow overlay (`WS_EX_TOOLWINDOW` + `WS_EX_NOACTIVATE`) with zero taskbar presence |
| **Keyboard Listener** | `pynput` | Global OS-level background hotkey interception |
| **Clipboard API** | `pyperclip` | Cross-platform OS clipboard read/write interface |
| **GUI HUD** | Flet (Flutter engine) *(Optional Phase)* | Reserved for optional full queue inspector overlay |
| **Packaging** | `PyInstaller` | Bundles into a standalone `.exe` without console |

---

## 3. Core User Flow & Shortcut Controls

### Key Controls & Triggers

1. **Master Toggle (`F4`)**:
   - Toggles **Queue Mode** `ON` or `OFF`.
   - Fires a clean, minimal dark charcoal Toast notification (`QPaste : ON` / `QPaste : OFF`) without stealing focus or flashing taskbar icons.
   - When **OFF**: Keyboard shortcuts pass through naturally; QPaste remains idle.
   - When **ON**: `Ctrl+C` and `Ctrl+V` are handled by QPaste's FIFO engine.

2. **Clear Queue (`Shift + F4`)**:
   - Clears all items currently stored in the FIFO queue and fires a `QPaste : Cleared` toast.

3. **System Tray Actions (Right-Click Menu)**:
   - **Toggle Queue Mode (F4)**: Toggles Queue Mode ON/OFF.
   - **Clear Queue (Shift+F4)**: Empties the queue.
   - **Start with Windows**: Automatically writes to the Windows Registry to launch QPaste silently on boot.
   - **Exit**: Safely terminates the background service.

4. **Copy Action (`Ctrl+C` / `Cmd+C`)**:
   - Intercepted when Queue Mode is `ON`.
   - Reads newly copied text via `pyperclip` and appends it to the back of the FIFO queue.

5. **Paste Action (`Ctrl+V` / `Cmd+V`)**:
   - Intercepted when Queue Mode is `ON`.
   - If Queue has items: Pops the oldest item (`pop(0)`), updates OS clipboard via `pyperclip`, and pastes it.
   - If Queue is empty: Falls back to normal clipboard behavior.

---

## 4. Functional Requirements

### 4.1 System Tray & Silent Launch Engine
- `REQ-1.1`: The app must launch 100% silently in the background, represented only by a System Tray icon without any window flashes on boot.
- `REQ-1.2`: Right-clicking the tray icon must provide control over application state and exit.
- `REQ-1.3`: The app must be capable of starting automatically on Windows boot via Registry.

### 4.2 Queue Management Engine
- `REQ-2.1`: Maintain a thread-safe list/deque of text strings.
- `REQ-2.2`: Provide a shortcut/button to clear the queue completely.

### 4.3 Native Toast Overlay
- `REQ-3.1`: State notifications must display at the bottom-right corner of the screen for 2 seconds.
- `REQ-3.2`: Must use `WS_EX_TOOLWINDOW` to guarantee zero presence on the Windows Taskbar or Alt+Tab switcher.
- `REQ-3.3`: Must use `WS_EX_NOACTIVATE` to prevent stealing window/keyboard focus from active applications.
- `REQ-3.4`: Uses a clean, minimal dark charcoal aesthetic with subtle dark borders.

---

## 5. Non-Functional Requirements

- **Performance**: Keyboard event latency must be $< 15\text{ ms}$ to prevent typing delay.
- **Resource Footprint**: Minimal CPU usage when idle.
- **Portability**: Must be compiled into a single `--noconsole` executable using PyInstaller.

---

## 6. Edge Cases & Handling Strategies

| Scenario | Risk | Mitigation Strategy |
| :--- | :--- | :--- |
| **Empty Queue on `Ctrl+V`** | App crash or lost paste | Passthrough to native OS clipboard paste |
| **Rapid `Ctrl+C` Spamming** | Race condition in clipboard | Debounce clipboard read operations by $50\text{ ms}$ |
| **Blocking pynput hooks** | Typing delay or `pynput` crash | Run all Toast Notifications in detached daemon threads |
