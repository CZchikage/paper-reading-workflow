# v12 — Stateful paper tracker

## Statuses
Exactly three:
- 🔴 To read
- 🟡 Review ready
- 🟢 Done

## Permanent deduplication
`data/paper_registry.json` stores every paper ever discovered.

Stable ID priority:
1. DOI
2. canonical proceedings/paper URL
3. hash(title + first author + year)

Weekly discovery:
- does not duplicate known papers;
- preserves status and notes;
- adds only genuinely unseen papers as `🔴 To read`.

## Reading-note integration
The `.agent` and `skills/paper-tracker/SKILL.md` instructions connect the
existing `paper-deep-reading` skill to the tracker.

After an AI deep-reading note is generated:
- status → `🟡 Review ready`
- note link is written into the tracker
- registry is updated too

After you review/approve it:
- status → `🟢 Done`

Done papers remain as history and are permanently excluded from rediscovery.
