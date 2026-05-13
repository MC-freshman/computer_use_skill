---
name: computer-use
description: Windows graphical interface operation for Codex through screenshots, coordinate-based mouse actions, keyboard input, clipboard paste, scrolling, drag-and-drop, and visual verification. Use when Codex needs to operate desktop apps, browsers, Office tools, PowerPoint layout, installers, dialogs, or any GUI that cannot be controlled reliably through files or shell commands alone.
---

# Computer Use

Use this skill to operate a Windows GUI with a screenshot-first loop. The bundled bridge is designed for precise visual work such as arranging PowerPoint objects, editing slides, selecting UI controls, or driving desktop apps that expose no useful CLI.

## Command Surface

Run all actions through `scripts/computer_use.py`.

```powershell
python scripts/computer_use.py observe --out .computer-use\screen.png --grid --cells 16
python scripts/computer_use.py click --x 640 --y 420
python scripts/computer_use.py drag --x1 420 --y1 320 --x2 760 --y2 320 --duration 0.45 --steps 36
python scripts/computer_use.py type --text "Quarterly plan"
python scripts/computer_use.py paste --text "Long or formatted-safe text"
python scripts/computer_use.py hotkey --keys ctrl,s
python scripts/computer_use.py scroll --x 900 --y 500 --dy -3
python scripts/computer_use.py active-window
python scripts/computer_use.py clipboard
python scripts/computer_use.py crop --x 300 --y 200 --w 500 --h 350 --out .computer-use\crop.png
python scripts/computer_use.py pixel --x 640 --y 420
python scripts/computer_use.py locate --needle button.png --threshold 0.94
python scripts/computer_use.py self-test
python scripts/computer_use.py gui-smoke-test
```

Every command prints JSON. Inspect `ok`, `result`, and `error` before continuing.

For complex JSON actions on PowerShell, prefer `--json-file action.json` because inline quote escaping is easy to get wrong.

## Workflow

1. Prefer file/API automation first. Use this skill when the needed state is only visible or controllable through the GUI.
2. Run `observe --grid` before acting. Use absolute screen coordinates from the saved PNG, not guessed UI labels.
3. Execute one small action at a time. Use `click`, `drag`, `hotkey`, `paste`, or `scroll`.
4. Run `observe` or `crop` after each material action and verify the visible result before continuing.
5. For layout work, use `crop`, `pixel`, grid overlays, and short drags. Avoid large imprecise moves.
6. For text, prefer `paste` over `type` unless the target blocks clipboard input.
7. Stop and ask the user before interacting with password fields, payment flows, account deletion, security prompts, or unknown destructive dialogs.

## Precision Practices

- Use `metrics` to confirm virtual desktop size and DPI awareness when coordinates appear offset.
- Use `move` to position the pointer before a difficult click, then `observe` if hover state matters.
- Use `drag --steps 30` or higher for slide object alignment, resizing, and selection boxes.
- Use keyboard shortcuts for deterministic Office work: `ctrl,a`, `ctrl,c`, `ctrl,v`, `ctrl+shift+...` where supported.
- Use `paste` for multi-line text; it preserves reliability by setting the clipboard then sending `ctrl,v`.
- `paste` overwrites the user's system clipboard. Use `clipboard` first if the current clipboard value matters.
- Use `crop` around the working area when reviewing fine details or reading small controls.
- Use `locate` only for exact or near-exact image templates. It is not OCR and does not understand text.

## Safety Rules

- Never click or type based only on an assumption; observe first.
- Keep destructive actions explicit and reversible. Prefer keyboard focus checks and screenshots before committing.
- Do not try to bypass UAC, lock screens, permission dialogs, or application security controls.
- Do not automate entry of secrets unless the user explicitly provides the secret and asks for that exact action.
- If screenshot capture fails or the desktop appears locked/obscured, stop.

## Local Notes

The bridge is Windows-only. It uses Python stdlib `ctypes` for input events and Pillow for screenshots/image helpers. If Pillow is missing, install it with `python -m pip install Pillow`.
