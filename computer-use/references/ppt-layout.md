# PPT Layout Workflow

Use `scripts/computer_use.py` for GUI-only PowerPoint work when file-level editing is insufficient.

## Recommended Loop

1. `observe --grid --cells 16` to get the whole slide and coordinates.
2. `crop` around the slide canvas or selected object for fine review.
3. Use `click` to select objects, `drag` for placement/resizing, and keyboard shortcuts for alignment panels.
4. Verify after every placement with `crop`.

## Practical Controls

- Selection box: drag from empty canvas space around objects.
- Move object: click object center, then drag center to the target.
- Resize object: click object, crop the bounding box, then drag a corner handle.
- Nudge: use arrow keys through `hotkey --keys left`, `hotkey --keys shift,right`, or PowerPoint shortcuts.
- Duplicate: `hotkey --keys ctrl,d`, then drag or nudge.
- Group: select multiple objects, then use `hotkey --keys ctrl,g`.
- Align: prefer PowerPoint's ribbon shortcuts when known; otherwise use visible menu clicks with screenshot verification.

## Accuracy Tips

- Use high `--steps` values on drags for smooth object movement.
- Use `pixel` when matching colors or checking whether a boundary line landed where expected.
- Use `paste` for text boxes after selecting or creating the target box.
- Avoid dragging from object edges unless resizing is intended.
