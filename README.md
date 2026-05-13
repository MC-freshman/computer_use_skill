# computer_use_skill

Codex skill for Windows GUI control through screenshots and coordinate-based mouse and keyboard actions. It is intended for desktop apps, browsers, Office tools, and visual layout work where shell/file automation is not enough.

## Install

Install the `computer-use` folder as a Codex skill. With a GitHub skill installer, use this repo path:

```text
MC-freshman/computer_use_skill / computer-use
```

For a local install, copy `computer-use` into your Codex skills directory and restart Codex.

## Use

```powershell
python computer-use\scripts\computer_use.py observe --grid
python computer-use\scripts\computer_use.py click --x 640 --y 420
python computer-use\scripts\computer_use.py drag --x1 420 --y1 320 --x2 760 --y2 320 --steps 36
python computer-use\scripts\computer_use.py paste --text "Hello"
```

## Test

```powershell
python computer-use\scripts\computer_use.py self-test
python computer-use\scripts\computer_use.py gui-smoke-test
```

`gui-smoke-test` opens a temporary local Tkinter window and verifies real click, paste, copy, drag, screenshot, and cleanup behavior.
