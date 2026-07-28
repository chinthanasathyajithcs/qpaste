# Proof of Concept (POC) Plan & Verification Report: QPaste Engine

> **Document Purpose:** Outline and document the technical validation results for QPaste's core features (global keyboard listener, FIFO queue, native toolwindow toast overlay, and system clipboard interoperability).
> **Status:** Completed & Verified  

---

## 1. POC Objectives

The core architecture validates 4 fundamental technical requirements:

1. **Global Keyboard Interception (`pynput`)**:
   - Verify global capture of `F4` (Master Toggle), `Shift + F4` (Clear Queue), `Ctrl+C`, and `Ctrl+V` across external applications.
2. **Thread Safety (`threading` + `pyperclip`)**:
   - Ensure `pynput`'s background listener thread can read/write the system clipboard via `pyperclip` without OS access locks.
3. **FIFO Queue Manipulation**:
   - Confirm that sequential copies store items in order, and sequential pastes consume items in FIFO order (`pop(0)`).
4. **Native ToolWindow Overlay (`WS_EX_TOOLWINDOW` | `WS_EX_NOACTIVATE`)**:
   - Verify that state notifications display cleanly in the bottom-right corner with zero taskbar presence and zero focus stealing.

---

## 2. Technical Architecture of the POC

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant OS as Operating System
    participant Listener as pynput Keyboard Listener
    participant Queue as FIFO Queue (deque)
    participant Toast as Native ToolWindow Overlay
    participant Clip as pyperclip Clipboard API

    User->>OS: Presses F4
    OS->>Listener: Key Event (F4)
    Listener->>Listener: Toggle Queue Mode (ACTIVE)
    Listener->>Toast: Show Toast ("QPaste : ON")

    User->>OS: Presses Ctrl+C (Text Snippet 1)
    OS->>Listener: Key Event (Ctrl+C)
    Listener->>Clip: Read Clipboard text
    Clip-->>Listener: Return "Snippet 1"
    Listener->>Queue: Push "Snippet 1"

    User->>OS: Presses Ctrl+C (Text Snippet 2)
    OS->>Listener: Key Event (Ctrl+C)
    Listener->>Clip: Read Clipboard text
    Clip-->>Listener: Return "Snippet 2"
    Listener->>Queue: Push "Snippet 2"

    User->>OS: Presses Ctrl+V
    OS->>Listener: Key Event (Ctrl+V)
    Listener->>Queue: Pop oldest ("Snippet 1")
    Queue-->>Listener: Return "Snippet 1"
    Listener->>Clip: Write "Snippet 1" to OS Clipboard
    Listener->>OS: Inject Ctrl+V paste event
```

---

## 3. POC Test Verification Checklist

| Test Case | Step | Expected Result | Pass / Fail |
| :--- | :--- | :--- | :--- |
| **TC-1: Toggle Mode** | Press `F4` in any app | State toggles `ACTIVE` / `PAUSED` and fires notification | ✅ Pass |
| **TC-2: Sequential Copy** | Copy 3 text snippets with Queue Mode `ACTIVE` | Queue contains 3 items in exact copied order | ✅ Pass |
| **TC-3: Sequential Paste** | Paste 3 times | Pasted items output in FIFO order (Item 1, then Item 2, then Item 3) | ✅ Pass |
| **TC-4: Mode Deactivation** | Press `F4` to turn OFF, then copy/paste | OS defaults to standard single-item copy/paste | ✅ Pass |
| **TC-5: Clear Queue** | Press `Shift + F4` with items in queue | Queue is completely emptied, fires `QPaste : Cleared` toast | ✅ Pass |
| **TC-6: Native ToolWindow Overlay** | Fire hotkey toast in any app | Toast pops up bottom-right with 0 taskbar icons & 0 focus stealing | ✅ Pass |
| **TC-7: Silent Background Startup** | Launch `python src/main.py` | App starts silently in system tray without any window flashing | ✅ Pass |

---

## 4. Next Implementation Step

Core implementation and automated unit tests (`pytest`) are complete. Proceed with packaging via `PyInstaller` into a standalone `.exe`.

