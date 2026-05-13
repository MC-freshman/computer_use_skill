#!/usr/bin/env python3
"""Windows GUI bridge for Codex computer-use skill.

The script intentionally exposes a small, JSON-printing command surface:
screenshot/observe, crop, pixel, locate, move, click, double-click, right-click,
drag, scroll, type, paste, hotkey, and wait.
"""

from __future__ import annotations

import argparse
import base64
import ctypes
from ctypes import wintypes
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from PIL import Image, ImageDraw, ImageGrab
except Exception:  # pragma: no cover - exercised only on missing dependency
    Image = None
    ImageDraw = None
    ImageGrab = None

IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
else:  # pragma: no cover - this bridge is intentionally Windows-only
    user32 = None
    kernel32 = None


SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x01000
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

WHEEL_DELTA = 120

VK: Dict[str, int] = {
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "shift": 0x10,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "pause": 0x13,
    "capslock": 0x14,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "pageup": 0x21,
    "pagedown": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "printscreen": 0x2C,
    "insert": 0x2D,
    "delete": 0x2E,
    "win": 0x5B,
    "meta": 0x5B,
    "apps": 0x5D,
    "numlock": 0x90,
    "scrolllock": 0x91,
    "semicolon": 0xBA,
    "equals": 0xBB,
    "comma": 0xBC,
    "minus": 0xBD,
    "period": 0xBE,
    "slash": 0xBF,
    "backtick": 0xC0,
    "lbracket": 0xDB,
    "backslash": 0xDC,
    "rbracket": 0xDD,
    "quote": 0xDE,
}

for i in range(10):
    VK[str(i)] = 0x30 + i
for i, ch in enumerate("abcdefghijklmnopqrstuvwxyz"):
    VK[ch] = 0x41 + i
for i in range(1, 25):
    VK[f"f{i}"] = 0x70 + i - 1


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


if IS_WINDOWS:
    user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL


def set_dpi_awareness() -> str:
    if not IS_WINDOWS:
        return "not-windows"
    # Prefer per-monitor v2. Ignore failure because older Windows builds only
    # support SetProcessDpiAwareness or SetProcessDPIAware.
    try:
        awareness_context_per_monitor_v2 = ctypes.c_void_p(-4)
        if user32.SetProcessDpiAwarenessContext(awareness_context_per_monitor_v2):
            return "per-monitor-v2"
    except Exception:
        pass
    try:
        shcore = ctypes.windll.shcore
        if shcore.SetProcessDpiAwareness(2) == 0:
            return "per-monitor"
    except Exception:
        pass
    try:
        if user32.SetProcessDPIAware():
            return "system"
    except Exception:
        pass
    return "unknown"


DPI_AWARENESS = set_dpi_awareness()


def fail(code: str, message: str, **details: Any) -> None:
    print_json({"ok": False, "error": {"code": code, "message": message, **details}})
    raise SystemExit(1)


def print_json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def require_windows() -> None:
    if not IS_WINDOWS:
        fail("UNSUPPORTED_OS", "computer_use.py only supports Windows.")


def require_pillow() -> None:
    if Image is None or ImageGrab is None:
        fail("MISSING_DEPENDENCY", "Pillow is required. Install with: python -m pip install Pillow")


def metrics() -> Dict[str, Any]:
    require_windows()
    x = int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
    y = int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
    w = int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN))
    h = int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))
    primary_w = int(user32.GetSystemMetrics(0))
    primary_h = int(user32.GetSystemMetrics(1))
    return {
        "virtual_screen": {"x": x, "y": y, "width": w, "height": h, "right": x + w, "bottom": y + h},
        "primary_screen": {"width": primary_w, "height": primary_h},
        "dpi_awareness": DPI_AWARENESS,
    }


def cursor_position() -> Dict[str, int]:
    require_windows()
    pt = POINT()
    if not user32.GetCursorPos(ctypes.byref(pt)):
        raise_windows_error("GetCursorPos failed")
    return {"x": int(pt.x), "y": int(pt.y)}


def active_window() -> Dict[str, Any]:
    require_windows()
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return {"hwnd": 0, "title": "", "pid": 0, "thread_id": 0}
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    pid = wintypes.DWORD(0)
    thread_id = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return {"hwnd": int(hwnd), "title": buffer.value, "pid": int(pid.value), "thread_id": int(thread_id)}


def raise_windows_error(prefix: str) -> None:
    err = kernel32.GetLastError() if kernel32 else 0
    fail("WINDOWS_API_ERROR", f"{prefix}. GetLastError={err}", win_error=err)


def validate_point(x: int, y: int) -> None:
    m = metrics()["virtual_screen"]
    if x < m["x"] or y < m["y"] or x >= m["right"] or y >= m["bottom"]:
        fail("OUT_OF_BOUNDS", "Point is outside the virtual desktop.", x=x, y=y, virtual_screen=m)


def validate_rect(x: int, y: int, w: int, h: int) -> None:
    if w <= 0 or h <= 0:
        fail("INVALID_RECT", "Width and height must be positive.", x=x, y=y, width=w, height=h)
    validate_point(x, y)
    validate_point(x + w - 1, y + h - 1)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def screenshot_image() -> Any:
    require_pillow()
    m = metrics()["virtual_screen"]
    try:
        img = ImageGrab.grab(
            bbox=(m["x"], m["y"], m["right"], m["bottom"]),
            all_screens=True,
        )
        return img.convert("RGB")
    except Exception as exc:
        fail("SCREENSHOT_FAILED", f"Could not capture the desktop: {exc}")


def add_grid(img: Any, cells: int = 16) -> Any:
    if ImageDraw is None:
        return img
    cells = max(2, min(int(cells), 64))
    out = img.copy()
    draw = ImageDraw.Draw(out)
    w, h = out.size
    grid_color = (255, 64, 64)
    text_bg = (255, 255, 255)
    text_fg = (0, 0, 0)
    for i in range(cells + 1):
        x = round(w * i / cells)
        y = round(h * i / cells)
        draw.line([(x, 0), (x, h)], fill=grid_color, width=1)
        draw.line([(0, y), (w, y)], fill=grid_color, width=1)
        if i < cells:
            label_x = f"x={x}"
            label_y = f"y={y}"
            draw.rectangle((x + 2, 2, x + 54, 16), fill=text_bg)
            draw.text((x + 4, 3), label_x, fill=text_fg)
            draw.rectangle((2, y + 2, 58, y + 16), fill=text_bg)
            draw.text((4, y + 3), label_y, fill=text_fg)
    return out


def add_screen_grid(img: Any, cells: int = 16, origin_x: int = 0, origin_y: int = 0) -> Any:
    if ImageDraw is None:
        return img
    cells = max(2, min(int(cells), 64))
    out = img.copy()
    draw = ImageDraw.Draw(out)
    w, h = out.size
    grid_color = (255, 64, 64)
    text_bg = (255, 255, 255)
    text_fg = (0, 0, 0)
    for i in range(cells + 1):
        local_x = round(w * i / cells)
        local_y = round(h * i / cells)
        screen_x = origin_x + local_x
        screen_y = origin_y + local_y
        draw.line([(local_x, 0), (local_x, h)], fill=grid_color, width=1)
        draw.line([(0, local_y), (w, local_y)], fill=grid_color, width=1)
        if i < cells:
            label_x = f"x={screen_x}"
            label_y = f"y={screen_y}"
            draw.rectangle((local_x + 2, 2, local_x + 76, 16), fill=text_bg)
            draw.text((local_x + 4, 3), label_x, fill=text_fg)
            draw.rectangle((2, local_y + 2, 82, local_y + 16), fill=text_bg)
            draw.text((4, local_y + 3), label_y, fill=text_fg)
    return out


def save_image(img: Any, out: str) -> str:
    path = Path(out).expanduser()
    ensure_parent(path)
    img.save(path)
    return str(path.resolve())


def image_payload(path: str, img: Any, include_base64: bool = False) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "path": path,
        "width": img.size[0],
        "height": img.size[1],
        "virtual_screen": metrics()["virtual_screen"],
    }
    if include_base64:
        with open(path, "rb") as f:
            result["png_base64"] = base64.b64encode(f.read()).decode("ascii")
    return result


def normalize_absolute(x: int, y: int) -> Tuple[int, int]:
    m = metrics()["virtual_screen"]
    # SendInput absolute coordinates are 0..65535 across the virtual desktop.
    # Use max(width - 1, 1) to avoid divide-by-zero on unusual desktops.
    ax = round((x - m["x"]) * 65535 / max(m["width"] - 1, 1))
    ay = round((y - m["y"]) * 65535 / max(m["height"] - 1, 1))
    return int(ax), int(ay)


def send_inputs(inputs: Sequence[INPUT]) -> None:
    require_windows()
    if not inputs:
        return
    array_type = INPUT * len(inputs)
    array = array_type(*inputs)
    sent = user32.SendInput(len(array), ctypes.cast(array, ctypes.POINTER(INPUT)), ctypes.sizeof(INPUT))
    if sent != len(inputs):
        raise_windows_error(f"SendInput sent {sent} of {len(inputs)} events")


def mouse_input(flags: int, dx: int = 0, dy: int = 0, data: int = 0) -> INPUT:
    event = INPUT()
    event.type = INPUT_MOUSE
    event.union.mi = MOUSEINPUT(dx, dy, data, flags, 0, None)
    return event


def key_input(vk: int, flags: int = 0, scan: int = 0) -> INPUT:
    event = INPUT()
    event.type = INPUT_KEYBOARD
    event.union.ki = KEYBDINPUT(vk, scan, flags, 0, None)
    return event


def move_to(x: int, y: int, dry_run: bool = False) -> Dict[str, Any]:
    validate_point(x, y)
    ax, ay = normalize_absolute(x, y)
    if not dry_run:
        send_inputs([mouse_input(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, ax, ay)])
    return {"x": x, "y": y, "dry_run": dry_run}


def button_flags(button: str) -> Tuple[int, int]:
    normalized = button.lower().strip()
    if normalized == "left":
        return MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP
    if normalized == "right":
        return MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
    if normalized in {"middle", "mid"}:
        return MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP
    fail("INVALID_BUTTON", "Button must be left, right, or middle.", button=button)
    raise AssertionError("unreachable")


def click_at(x: int, y: int, button: str = "left", clicks: int = 1, interval: float = 0.08, dry_run: bool = False) -> Dict[str, Any]:
    validate_point(x, y)
    down, up = button_flags(button)
    if not dry_run:
        move_to(x, y)
        time.sleep(0.03)
        for idx in range(max(1, clicks)):
            send_inputs([mouse_input(down), mouse_input(up)])
            if idx != clicks - 1:
                time.sleep(max(0.0, interval))
    return {"x": x, "y": y, "button": button, "clicks": clicks, "dry_run": dry_run}


def drag_to(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    button: str = "left",
    duration: float = 0.35,
    steps: int = 28,
    dry_run: bool = False,
) -> Dict[str, Any]:
    validate_point(x1, y1)
    validate_point(x2, y2)
    down, up = button_flags(button)
    steps = max(2, min(int(steps), 240))
    duration = max(0.0, float(duration))
    if not dry_run:
        move_to(x1, y1)
        time.sleep(0.05)
        send_inputs([mouse_input(down)])
        time.sleep(0.05)
        delay = duration / steps if steps else 0
        for i in range(1, steps + 1):
            t = i / steps
            x = round(x1 + (x2 - x1) * t)
            y = round(y1 + (y2 - y1) * t)
            move_to(x, y)
            if delay:
                time.sleep(delay)
        send_inputs([mouse_input(up)])
    return {
        "start": {"x": x1, "y": y1},
        "end": {"x": x2, "y": y2},
        "button": button,
        "duration": duration,
        "steps": steps,
        "dry_run": dry_run,
    }


def scroll_at(x: int, y: int, dx: int = 0, dy: int = 0, dry_run: bool = False) -> Dict[str, Any]:
    validate_point(x, y)
    if dx == 0 and dy == 0:
        fail("NO_SCROLL_DELTA", "At least one of dx or dy must be non-zero.")
    if not dry_run:
        move_to(x, y)
        time.sleep(0.03)
        events: List[INPUT] = []
        if dy:
            events.append(mouse_input(MOUSEEVENTF_WHEEL, data=int(dy) * WHEEL_DELTA))
        if dx:
            events.append(mouse_input(MOUSEEVENTF_HWHEEL, data=int(dx) * WHEEL_DELTA))
        send_inputs(events)
    return {"x": x, "y": y, "dx": dx, "dy": dy, "dry_run": dry_run}


def parse_keys(keys: str) -> List[int]:
    parts = [part.strip().lower() for part in keys.replace("+", ",").split(",") if part.strip()]
    if not parts:
        fail("INVALID_KEYS", "Provide at least one key.")
    result = []
    for part in parts:
        if part not in VK:
            fail("UNKNOWN_KEY", "Unknown key name.", key=part, allowed=sorted(VK.keys()))
        result.append(VK[part])
    return result


def hotkey(keys: str, dry_run: bool = False) -> Dict[str, Any]:
    vks = parse_keys(keys)
    if not dry_run:
        events = [key_input(vk) for vk in vks]
        events.extend(key_input(vk, KEYEVENTF_KEYUP) for vk in reversed(vks))
        send_inputs(events)
    return {"keys": keys, "dry_run": dry_run}


def type_text(text: str, interval: float = 0.0, allow_control: bool = False, dry_run: bool = False) -> Dict[str, Any]:
    if not allow_control:
        bad = [ch for ch in text if ord(ch) < 32 and ch not in "\r\n\t"]
        if bad:
            fail("CONTROL_CHARACTERS", "Text contains control characters. Pass --allow-control to allow them.")
    if len(text) > 4000:
        fail("TEXT_TOO_LONG", "Use paste for long text or pass shorter text.", length=len(text), limit=4000)
    if not dry_run:
        for ch in text:
            code = ord(ch)
            if code > 0xFFFF:
                # Send surrogate pair for non-BMP characters.
                code -= 0x10000
                units = [0xD800 + (code >> 10), 0xDC00 + (code & 0x3FF)]
            else:
                units = [code]
            for unit in units:
                send_inputs([key_input(0, KEYEVENTF_UNICODE, unit), key_input(0, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, unit)])
            if interval:
                time.sleep(max(0.0, interval))
    return {"length": len(text), "dry_run": dry_run}


def set_clipboard_text(text: str) -> None:
    require_windows()
    GMEM_MOVEABLE = 0x0002
    CF_UNICODETEXT = 13
    data = (text + "\0").encode("utf-16le")
    h_global = None
    if not user32.OpenClipboard(None):
        raise_windows_error("OpenClipboard failed")
    try:
        if not user32.EmptyClipboard():
            raise_windows_error("EmptyClipboard failed")
        h_global = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not h_global:
            raise_windows_error("GlobalAlloc failed")
        locked = kernel32.GlobalLock(h_global)
        if not locked:
            raise_windows_error("GlobalLock failed")
        try:
            ctypes.memmove(locked, data, len(data))
        finally:
            kernel32.GlobalUnlock(h_global)
        if not user32.SetClipboardData(CF_UNICODETEXT, h_global):
            raise_windows_error("SetClipboardData failed")
        h_global = None
        # Clipboard owns h_global after SetClipboardData succeeds.
    finally:
        user32.CloseClipboard()
        if h_global:
            kernel32.GlobalFree(h_global)


def get_clipboard_text() -> Dict[str, Any]:
    require_windows()
    CF_UNICODETEXT = 13
    if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
        return {"text": "", "length": 0, "available": False}
    if not user32.OpenClipboard(None):
        raise_windows_error("OpenClipboard failed")
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            raise_windows_error("GetClipboardData failed")
        locked = kernel32.GlobalLock(handle)
        if not locked:
            raise_windows_error("GlobalLock failed")
        try:
            text = ctypes.wstring_at(locked)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()
    return {"text": text, "length": len(text), "available": True}


def paste_text(text: str, dry_run: bool = False) -> Dict[str, Any]:
    if len(text) > 50000:
        fail("TEXT_TOO_LONG", "Clipboard paste text is too long.", length=len(text), limit=50000)
    if not dry_run:
        set_clipboard_text(text)
        time.sleep(0.05)
        hotkey("ctrl,v")
    return {"length": len(text), "dry_run": dry_run}


def crop_image(x: int, y: int, w: int, h: int, out: str, grid: bool = False, cells: int = 8, include_base64: bool = False) -> Dict[str, Any]:
    validate_rect(x, y, w, h)
    img = screenshot_image()
    m = metrics()["virtual_screen"]
    crop = img.crop((x - m["x"], y - m["y"], x - m["x"] + w, y - m["y"] + h))
    if grid:
        crop = add_screen_grid(crop, cells, x, y)
    path = save_image(crop, out)
    return image_payload(path, crop, include_base64)


def pixel_at(x: int, y: int) -> Dict[str, Any]:
    validate_point(x, y)
    img = screenshot_image()
    m = metrics()["virtual_screen"]
    rgb = img.getpixel((x - m["x"], y - m["y"]))
    return {"x": x, "y": y, "rgb": list(rgb), "hex": "#{:02x}{:02x}{:02x}".format(*rgb)}


def load_image(path: str) -> Any:
    require_pillow()
    try:
        return Image.open(path).convert("RGB")
    except Exception as exc:
        fail("IMAGE_LOAD_FAILED", f"Could not load image: {exc}", path=path)


def locate_template(needle_path: str, threshold: float = 0.96, haystack_path: Optional[str] = None, max_results: int = 10) -> Dict[str, Any]:
    require_pillow()
    if threshold < 0.5 or threshold > 1.0:
        fail("INVALID_THRESHOLD", "Threshold must be between 0.5 and 1.0.", threshold=threshold)
    haystack = load_image(haystack_path) if haystack_path else screenshot_image()
    origin = {"x": 0, "y": 0} if haystack_path else {"x": metrics()["virtual_screen"]["x"], "y": metrics()["virtual_screen"]["y"]}
    needle = load_image(needle_path)
    hw, hh = haystack.size
    nw, nh = needle.size
    if nw > hw or nh > hh:
        fail("NEEDLE_TOO_LARGE", "Needle image is larger than haystack.", needle=needle.size, haystack=haystack.size)

    # Keep this deterministic and dependency-light. It is intended for small UI
    # snippets, not large-scale computer vision.
    hay_pixels = haystack.load()
    needle_pixels = needle.load()
    sample_points = []
    grid = max(1, int(math.sqrt(max(nw * nh / 160, 1))))
    for yy in range(0, nh, grid):
        for xx in range(0, nw, grid):
            sample_points.append((xx, yy))
    if (nw - 1, nh - 1) not in sample_points:
        sample_points.append((nw - 1, nh - 1))

    max_error = (1.0 - threshold) * 255.0 * 3.0
    matches = []
    for y in range(0, hh - nh + 1):
        for x in range(0, hw - nw + 1):
            total_error = 0.0
            failed = False
            for index, (sx, sy) in enumerate(sample_points, start=1):
                hp = hay_pixels[x + sx, y + sy]
                np = needle_pixels[sx, sy]
                total_error += abs(hp[0] - np[0]) + abs(hp[1] - np[1]) + abs(hp[2] - np[2])
                if total_error / (index * 255.0 * 3.0) > (1.0 - threshold):
                    failed = True
                    break
            if failed:
                continue
            score = 1.0 - (total_error / (len(sample_points) * 255.0 * 3.0))
            if score >= threshold:
                screen_x = origin["x"] + x
                screen_y = origin["y"] + y
                matches.append({
                    "x": screen_x,
                    "y": screen_y,
                    "local_x": x,
                    "local_y": y,
                    "width": nw,
                    "height": nh,
                    "center": {"x": screen_x + nw // 2, "y": screen_y + nh // 2},
                    "local_center": {"x": x + nw // 2, "y": y + nh // 2},
                    "score": round(score, 4),
                })
                if len(matches) >= max_results:
                    return {"matches": matches, "count": len(matches), "truncated": True}
    return {"matches": matches, "count": len(matches), "truncated": False}


def read_text_arg(value: Optional[str], file_value: Optional[str]) -> str:
    if value is not None and file_value is not None:
        fail("ARGUMENT_CONFLICT", "Use either --text or --text-file, not both.")
    if file_value is not None:
        try:
            return Path(file_value).read_text(encoding="utf-8")
        except Exception as exc:
            fail("TEXT_FILE_FAILED", f"Could not read text file: {exc}", path=file_value)
    if value is None:
        fail("MISSING_TEXT", "Provide --text or --text-file.")
    return value


def require_fields(payload: Dict[str, Any], fields: Sequence[str]) -> None:
    missing = [field for field in fields if field not in payload]
    if missing:
        fail("MISSING_FIELDS", "JSON action is missing required fields.", missing=missing)


def default_out(name: str) -> str:
    base = Path.cwd() / ".computer-use"
    base.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    return str(base / f"{name}-{ts}.png")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Windows GUI bridge for Codex computer-use skill.")
    parser.add_argument("--json", dest="json_action", help="Run one action from a JSON object.")
    parser.add_argument("--json-file", dest="json_file", help="Run one action from a UTF-8 JSON file.")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("metrics")

    p = sub.add_parser("pos")

    p = sub.add_parser("active-window")

    p = sub.add_parser("observe")
    p.add_argument("--out", default=None)
    p.add_argument("--grid", action="store_true")
    p.add_argument("--cells", type=int, default=16)
    p.add_argument("--base64", action="store_true")

    p = sub.add_parser("screenshot")
    p.add_argument("--out", default=None)
    p.add_argument("--grid", action="store_true")
    p.add_argument("--cells", type=int, default=16)
    p.add_argument("--base64", action="store_true")

    p = sub.add_parser("crop")
    p.add_argument("--x", type=int, required=True)
    p.add_argument("--y", type=int, required=True)
    p.add_argument("--w", type=int, required=True)
    p.add_argument("--h", type=int, required=True)
    p.add_argument("--out", default=None)
    p.add_argument("--grid", action="store_true")
    p.add_argument("--cells", type=int, default=8)
    p.add_argument("--base64", action="store_true")

    p = sub.add_parser("pixel")
    p.add_argument("--x", type=int, required=True)
    p.add_argument("--y", type=int, required=True)

    p = sub.add_parser("move")
    p.add_argument("--x", type=int, required=True)
    p.add_argument("--y", type=int, required=True)
    p.add_argument("--dry-run", action="store_true")

    for name, clicks, button in [("click", 1, "left"), ("double-click", 2, "left"), ("right-click", 1, "right")]:
        p = sub.add_parser(name)
        p.add_argument("--x", type=int, required=True)
        p.add_argument("--y", type=int, required=True)
        p.add_argument("--button", default=button)
        p.add_argument("--clicks", type=int, default=clicks)
        p.add_argument("--interval", type=float, default=0.08)
        p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("drag")
    p.add_argument("--x1", type=int, required=True)
    p.add_argument("--y1", type=int, required=True)
    p.add_argument("--x2", type=int, required=True)
    p.add_argument("--y2", type=int, required=True)
    p.add_argument("--button", default="left")
    p.add_argument("--duration", type=float, default=0.35)
    p.add_argument("--steps", type=int, default=28)
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("scroll")
    p.add_argument("--x", type=int, required=True)
    p.add_argument("--y", type=int, required=True)
    p.add_argument("--dx", type=int, default=0)
    p.add_argument("--dy", type=int, default=0)
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("type")
    p.add_argument("--text")
    p.add_argument("--text-file")
    p.add_argument("--interval", type=float, default=0.0)
    p.add_argument("--allow-control", action="store_true")
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("paste")
    p.add_argument("--text")
    p.add_argument("--text-file")
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("clipboard")

    p = sub.add_parser("hotkey")
    p.add_argument("--keys", required=True)
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("wait")
    p.add_argument("--seconds", type=float, default=1.0)

    p = sub.add_parser("locate")
    p.add_argument("--needle", required=True)
    p.add_argument("--haystack")
    p.add_argument("--threshold", type=float, default=0.96)
    p.add_argument("--max-results", type=int, default=10)

    p = sub.add_parser("self-test")
    p.add_argument("--out-dir", default=None)
    p.add_argument("--include-input", action="store_true", help="Also test dry-run input actions.")

    p = sub.add_parser("gui-smoke-test")
    p.add_argument("--out-dir", default=None)

    p = sub.add_parser("_smoke-window")
    p.add_argument("--state-file", required=True)
    p.add_argument("--stop-file", required=True)

    return parser


def dispatch(args: argparse.Namespace) -> Dict[str, Any]:
    command = args.command
    if command is None and not args.json_action and not args.json_file:
        fail("MISSING_COMMAND", "Provide a command, --json, or --json-file action.")

    if args.json_action and args.json_file:
        fail("ARGUMENT_CONFLICT", "Use either --json or --json-file, not both.")

    if args.json_action or args.json_file:
        json_text = args.json_action
        if args.json_file:
            try:
                json_text = Path(args.json_file).read_text(encoding="utf-8-sig")
            except Exception as exc:
                fail("JSON_FILE_FAILED", f"Could not read JSON file: {exc}", path=args.json_file)
        try:
            payload = json.loads(json_text or "")
        except json.JSONDecodeError as exc:
            fail("INVALID_JSON", f"Could not parse JSON action: {exc}")
        return dispatch_json(payload)

    if command == "metrics":
        return metrics()
    if command == "pos":
        return cursor_position()
    if command == "active-window":
        return active_window()
    if command in {"observe", "screenshot"}:
        img = screenshot_image()
        if args.grid:
            m = metrics()["virtual_screen"]
            img = add_screen_grid(img, args.cells, m["x"], m["y"])
        out = args.out or default_out("screen")
        path = save_image(img, out)
        return image_payload(path, img, args.base64)
    if command == "crop":
        out = args.out or default_out("crop")
        return crop_image(args.x, args.y, args.w, args.h, out, args.grid, args.cells, args.base64)
    if command == "pixel":
        return pixel_at(args.x, args.y)
    if command == "move":
        return move_to(args.x, args.y, args.dry_run)
    if command in {"click", "double-click", "right-click"}:
        return click_at(args.x, args.y, args.button, args.clicks, args.interval, args.dry_run)
    if command == "drag":
        return drag_to(args.x1, args.y1, args.x2, args.y2, args.button, args.duration, args.steps, args.dry_run)
    if command == "scroll":
        return scroll_at(args.x, args.y, args.dx, args.dy, args.dry_run)
    if command == "type":
        return type_text(read_text_arg(args.text, args.text_file), args.interval, args.allow_control, args.dry_run)
    if command == "paste":
        return paste_text(read_text_arg(args.text, args.text_file), args.dry_run)
    if command == "clipboard":
        return get_clipboard_text()
    if command == "hotkey":
        return hotkey(args.keys, args.dry_run)
    if command == "wait":
        seconds = max(0.0, float(args.seconds))
        time.sleep(seconds)
        return {"seconds": seconds}
    if command == "locate":
        return locate_template(args.needle, args.threshold, args.haystack, args.max_results)
    if command == "self-test":
        return self_test(args.out_dir, args.include_input)
    if command == "gui-smoke-test":
        return gui_smoke_test(args.out_dir)
    if command == "_smoke-window":
        return smoke_window(args.state_file, args.stop_file)
    fail("UNKNOWN_COMMAND", "Unknown command.", command=command)
    raise AssertionError("unreachable")


def dispatch_json(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        fail("INVALID_JSON_ACTION", "JSON action must be an object.")
    action = str(payload.get("action", "")).strip().lower()
    dry_run = bool(payload.get("dry_run", False))
    if action in {"metrics"}:
        return metrics()
    if action in {"pos", "position"}:
        return cursor_position()
    if action in {"active-window", "window"}:
        return active_window()
    if action in {"observe", "screenshot"}:
        img = screenshot_image()
        if payload.get("grid"):
            m = metrics()["virtual_screen"]
            img = add_screen_grid(img, int(payload.get("cells", 16)), m["x"], m["y"])
        out = str(payload.get("out") or default_out("screen"))
        path = save_image(img, out)
        return image_payload(path, img, bool(payload.get("base64", False)))
    if action == "crop":
        require_fields(payload, ["x", "y", "w", "h"])
        return crop_image(
            int(payload["x"]),
            int(payload["y"]),
            int(payload["w"]),
            int(payload["h"]),
            str(payload.get("out") or default_out("crop")),
            bool(payload.get("grid", False)),
            int(payload.get("cells", 8)),
            bool(payload.get("base64", False)),
        )
    if action == "pixel":
        require_fields(payload, ["x", "y"])
        return pixel_at(int(payload["x"]), int(payload["y"]))
    if action == "move":
        require_fields(payload, ["x", "y"])
        return move_to(int(payload["x"]), int(payload["y"]), dry_run)
    if action == "click":
        require_fields(payload, ["x", "y"])
        return click_at(
            int(payload["x"]),
            int(payload["y"]),
            str(payload.get("button", "left")),
            int(payload.get("clicks", 1)),
            float(payload.get("interval", 0.08)),
            dry_run,
        )
    if action == "drag":
        require_fields(payload, ["x1", "y1", "x2", "y2"])
        return drag_to(
            int(payload["x1"]),
            int(payload["y1"]),
            int(payload["x2"]),
            int(payload["y2"]),
            str(payload.get("button", "left")),
            float(payload.get("duration", 0.35)),
            int(payload.get("steps", 28)),
            dry_run,
        )
    if action == "scroll":
        require_fields(payload, ["x", "y"])
        return scroll_at(int(payload["x"]), int(payload["y"]), int(payload.get("dx", 0)), int(payload.get("dy", 0)), dry_run)
    if action == "type":
        return type_text(str(payload.get("text", "")), float(payload.get("interval", 0.0)), bool(payload.get("allow_control", False)), dry_run)
    if action == "paste":
        return paste_text(str(payload.get("text", "")), dry_run)
    if action == "clipboard":
        return get_clipboard_text()
    if action == "hotkey":
        require_fields(payload, ["keys"])
        return hotkey(str(payload["keys"]), dry_run)
    if action == "wait":
        seconds = max(0.0, float(payload.get("seconds", 1.0)))
        time.sleep(seconds)
        return {"seconds": seconds}
    if action == "locate":
        require_fields(payload, ["needle"])
        return locate_template(str(payload["needle"]), float(payload.get("threshold", 0.96)), payload.get("haystack"), int(payload.get("max_results", 10)))
    fail("UNKNOWN_ACTION", "Unknown JSON action.", action=action)
    raise AssertionError("unreachable")


def self_test(out_dir: Optional[str], include_input: bool = False) -> Dict[str, Any]:
    require_windows()
    require_pillow()
    target_dir = Path(out_dir) if out_dir else Path.cwd() / ".computer-use" / "self-test"
    target_dir.mkdir(parents=True, exist_ok=True)
    m = metrics()
    shot_path = target_dir / "screen.png"
    grid_path = target_dir / "screen-grid.png"
    crop_path = target_dir / "crop.png"
    img = screenshot_image()
    save_image(img, str(shot_path))
    save_image(add_grid(img, 8), str(grid_path))
    vs = m["virtual_screen"]
    cx = vs["x"] + max(0, vs["width"] // 2 - 120)
    cy = vs["y"] + max(0, vs["height"] // 2 - 90)
    crop = crop_image(cx, cy, min(240, vs["width"]), min(180, vs["height"]), str(crop_path), True, 6)
    pix = pixel_at(vs["x"] + vs["width"] // 2, vs["y"] + vs["height"] // 2)
    dry_runs = {
        "move": move_to(vs["x"] + vs["width"] // 2, vs["y"] + vs["height"] // 2, True),
        "click": click_at(vs["x"] + vs["width"] // 2, vs["y"] + vs["height"] // 2, dry_run=True),
        "drag": drag_to(vs["x"] + 10, vs["y"] + 10, vs["x"] + 20, vs["y"] + 20, dry_run=True),
        "scroll": scroll_at(vs["x"] + vs["width"] // 2, vs["y"] + vs["height"] // 2, dy=-1, dry_run=True),
        "type": type_text("abc", dry_run=True),
        "paste": paste_text("abc", dry_run=True),
        "hotkey": hotkey("ctrl,c", dry_run=True),
    }
    if include_input:
        pos_before = cursor_position()
        move_to(pos_before["x"], pos_before["y"])
    return {
        "metrics": m,
        "files": {
            "screen": str(shot_path.resolve()),
            "grid": str(grid_path.resolve()),
            "crop": crop["path"],
        },
        "pixel": pix,
        "dry_runs": dry_runs,
    }


def gui_smoke_test(out_dir: Optional[str]) -> Dict[str, Any]:
    require_windows()
    require_pillow()
    target_dir = Path(out_dir) if out_dir else Path.cwd() / ".computer-use" / "gui-smoke-test"
    target_dir.mkdir(parents=True, exist_ok=True)
    state_path = target_dir / "smoke-state.json"
    stop_path = target_dir / "smoke-stop"
    if state_path.exists():
        state_path.unlink()
    if stop_path.exists():
        stop_path.unlink()
    proc = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "_smoke-window",
            "--state-file",
            str(state_path),
            "--stop-file",
            str(stop_path),
        ],
        cwd=str(Path.cwd()),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    coords = None
    deadline = time.time() + 8
    while time.time() < deadline:
        if proc.poll() is not None:
            stdout, stderr = proc.communicate(timeout=1)
            fail("GUI_SMOKE_WINDOW_EXITED", "Smoke test window exited before becoming ready.", stdout=stdout, stderr=stderr)
        if state_path.exists():
            try:
                coords = json.loads(state_path.read_text(encoding="utf-8"))
                if coords.get("ready"):
                    break
            except Exception:
                pass
        time.sleep(0.1)
    if not coords or not coords.get("ready"):
        proc.terminate()
        fail("GUI_SMOKE_TIMEOUT", "Smoke test window did not become ready.")

    ex = int(coords["entry"]["x"])
    ey = int(coords["entry"]["y"])
    dx1 = int(coords["drag"]["x1"])
    dy1 = int(coords["drag"]["y1"])
    dx2 = int(coords["drag"]["x2"])
    dy2 = int(coords["drag"]["y2"])

    test_text = "computer-use gui smoke 789"
    click_at(ex, ey)
    paste_text(test_text)
    time.sleep(0.2)
    hotkey("ctrl,a")
    hotkey("ctrl,c")
    time.sleep(0.2)
    clip = get_clipboard_text()
    drag_to(dx1, dy1, dx2, dy2, duration=0.35, steps=36)
    time.sleep(0.2)
    shot_path = target_dir / "gui-smoke.png"
    observe_img = screenshot_image()
    save_image(observe_img, str(shot_path))
    try:
        coords = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as exc:
        proc.terminate()
        fail("GUI_SMOKE_STATE_FAILED", f"Could not read smoke window state: {exc}")
    actual_entry = str(coords.get("entry_text", ""))
    dragged_x = int(coords.get("drag_box_center", {}).get("x", 0))
    stop_path.write_text("stop", encoding="utf-8")
    try:
        stdout, stderr = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.terminate()
        stdout, stderr = proc.communicate(timeout=3)
    returncode = proc.returncode

    if actual_entry != test_text:
        fail("GUI_SMOKE_TEXT_FAILED", "Text was not pasted into the test entry.", expected=test_text, actual=actual_entry)
    if clip.get("text") != test_text:
        fail("GUI_SMOKE_CLIPBOARD_FAILED", "Copied text did not match the test entry.", expected=test_text, actual=clip.get("text"))
    if dragged_x < dx2 - 35:
        fail("GUI_SMOKE_DRAG_FAILED", "Canvas object drag did not move far enough.", expected_min_x=dx2 - 35, actual_x=dragged_x)
    return {
        "text": actual_entry,
        "clipboard": clip,
        "drag_box_center": coords.get("drag_box_center"),
        "screenshot": str(shot_path.resolve()),
        "window_stdout": stdout.strip(),
        "window_stderr": stderr.strip(),
        "closed": returncode == 0,
    }


def smoke_window(state_file: str, stop_file: str) -> Dict[str, Any]:
    try:
        import tkinter as tk
    except Exception as exc:
        fail("MISSING_TKINTER", f"Tkinter is required for gui-smoke-test: {exc}")

    state_path = Path(state_file)
    stop_path = Path(stop_file)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    root = tk.Tk()
    root.title("computer-use smoke test")
    root.geometry("520x300+120+120")
    root.attributes("-topmost", True)
    label = tk.Label(root, text="Computer Use Smoke Test", font=("Segoe UI", 16))
    label.pack(pady=12)
    entry = tk.Entry(root, width=42, font=("Segoe UI", 12))
    entry.pack(pady=10)
    canvas = tk.Canvas(root, width=420, height=96, bg="white", highlightthickness=1, highlightbackground="#777")
    canvas.pack(pady=14)
    box = canvas.create_rectangle(30, 28, 82, 80, fill="#2f80ed", outline="#174ea6", width=2)
    drag_state = {"x": 0, "y": 0}

    def on_press(event: Any) -> None:
        drag_state["x"] = event.x
        drag_state["y"] = event.y

    def on_drag(event: Any) -> None:
        dx = event.x - drag_state["x"]
        dy = event.y - drag_state["y"]
        canvas.move(box, dx, dy)
        drag_state["x"] = event.x
        drag_state["y"] = event.y

    canvas.tag_bind(box, "<ButtonPress-1>", on_press)
    canvas.tag_bind(box, "<B1-Motion>", on_drag)
    close = tk.Button(root, text="Close", command=root.destroy)
    close.pack(pady=8)

    def write_state() -> None:
        if stop_path.exists():
            root.destroy()
            return
        root.update_idletasks()
        state = {
            "ready": True,
            "entry": {
                "x": root.winfo_rootx() + entry.winfo_x() + 24,
                "y": root.winfo_rooty() + entry.winfo_y() + entry.winfo_height() // 2,
            },
            "drag": {
                "x1": root.winfo_rootx() + canvas.winfo_x() + 56,
                "y1": root.winfo_rooty() + canvas.winfo_y() + 54,
                "x2": root.winfo_rootx() + canvas.winfo_x() + 330,
                "y2": root.winfo_rooty() + canvas.winfo_y() + 54,
            },
            "close": {
                "x": root.winfo_rootx() + close.winfo_x() + close.winfo_width() // 2,
                "y": root.winfo_rooty() + close.winfo_y() + close.winfo_height() // 2,
            },
            "entry_text": entry.get(),
            "drag_box_center": {
                "x": root.winfo_rootx() + canvas.winfo_x() + int((canvas.coords(box)[0] + canvas.coords(box)[2]) / 2),
                "y": root.winfo_rooty() + canvas.winfo_y() + int((canvas.coords(box)[1] + canvas.coords(box)[3]) / 2),
            },
        }
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        root.after(100, write_state)

    root.after(300, lambda: root.attributes("-topmost", False))
    root.after(100, write_state)
    root.mainloop()
    return {"closed": True}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = dispatch(args)
        print_json({"ok": True, "action": args.command or "json", "result": result})
        return 0
    except SystemExit:
        raise
    except Exception as exc:
        print_json({"ok": False, "error": {"code": "UNHANDLED_EXCEPTION", "message": str(exc)}})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
