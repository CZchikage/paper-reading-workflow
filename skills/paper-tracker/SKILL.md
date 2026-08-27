---
name: paper-tracker
description: Maintain persistent paper reading states, deduplicate papers, and connect discovery with reading notes.
---

# Paper Tracker

All tracker-related instructions and text must be in English.

Valid statuses are exactly:
- 🔴 To read
- 🟡 Review ready
- 🟢 Done

`data/paper_registry.json` is the source of truth.
`reading_queue.md` is the human-facing tracker.

After FAST or DEEP reading creates/updates a note:
- set status to `🟡 Review ready`
- add the note link
- update both registry and queue

Only after the user explicitly confirms they reviewed/finished/approved the paper:
- set status to `🟢 Done`

Never mark Done merely because the AI note exists.

Never re-add a paper already present in the registry.
