---
name: paper-tracker
description: Maintain persistent paper reading states, deduplicate papers, and keep active reading queue separate from completed reading history.
---

# Paper Tracker

All tracker-related instructions and text must be in English.

Valid statuses are exactly:
- 🔴 To read
- 🟡 Review ready
- 🟢 Done

Files:
- `reading_queue.md`: active work only (`🔴 To read`, `🟡 Review ready`)
- `reading_history.md`: completed work only (`🟢 Done`)
- `data/paper_registry.json`: permanent source of truth and deduplication database

## Lifecycle

### New paper
Set:
`🔴 To read`

Keep it in `reading_queue.md`.

### Reading note completed
After FAST or DEEP reading creates or updates a note:
- set status to `🟡 Review ready`
- add the note link
- update `reading_queue.md`
- update `data/paper_registry.json`

Do not add it to history yet.

### User review completed
Only after the user explicitly confirms they reviewed/finished/approved the paper:
- set status to `🟢 Done`
- remove it from `reading_queue.md`
- add it to `reading_history.md`
- preserve the note link
- update `data/paper_registry.json`

Never mark Done merely because an AI note exists.

## Deduplication

Never re-add a paper already present in the registry.

Done papers remain permanently registered even though they no longer appear in the active queue.
