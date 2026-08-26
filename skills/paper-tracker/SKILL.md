---
name: paper-tracker
description: Maintain persistent paper reading states, deduplicate discovered papers, and connect paper discovery with paper-deep-reading notes.
---

# Paper Tracker

Use exactly these statuses:
- 🔴 To read
- 🟡 Review ready
- 🟢 Done

`data/paper_registry.json` is the source of truth for deduplication/history.
`reading_queue.md` is the human-facing view.

After `paper-deep-reading` successfully generates a note:
- set status to `🟡 Review ready`
- add the note link
- update registry and queue together.

After the user reviews/approves the note:
- set status to `🟢 Done`
- keep the note link.

Never re-add a registry paper as a new paper.
