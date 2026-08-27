---
name: paper-deep-reading
description: Read academic papers in FAST or DEEP mode and produce structured English research notes with critical analysis. FAST is the default. DEEP overrides FAST whenever the user explicitly asks for deep reading, theorem-by-theorem analysis, proof reconstruction, exhaustive figure/table/equation review, reproducibility analysis, detailed related-work positioning, appendix inspection, or a full critical review.
---

# Paper Reading

## Overview

Turn an academic paper into a durable English research note.

FAST is the default mode.

DEEP always overrides FAST when explicitly requested, even if FAST is also mentioned.

Read `references/note-schema.md` before creating or revising a saved note.

## Mode Selection

### FAST mode — default

Use FAST unless the user explicitly triggers DEEP.

FAST should focus on:
- metadata
- TL;DR
- motivation and core idea
- main contribution
- key method
- key theorem/result
- main evaluation/result
- strengths
- limitations
- takeaways
- what deserves deeper reading

FAST should normally skip:
- exhaustive appendix reading
- theorem-by-theorem proof reconstruction
- every figure/table/equation
- broad related-work searches
- exhaustive reproducibility analysis

### DEEP mode — explicit override

Use DEEP if the user explicitly asks for any of the following:
- deep read / deep reading
- deep analysis
- theorem-by-theorem analysis
- proof reconstruction
- derivation
- inspect the appendix carefully
- exhaustive figures/tables/equations
- reproducibility analysis
- full critical review
- detailed related-work positioning
- verify every assumption or main claim

If both FAST and DEEP are mentioned, use DEEP.

## Workflow

### 1. Resolve the paper source

Prefer:
1. official conference proceedings
2. publisher page / DOI
3. author or project page
4. arXiv only when no better source is available

If a local PDF is provided, read it directly.

Inside the repository, check for an existing note before creating a duplicate.

Never invent metadata. Use `Unknown` or `TBD` when necessary.

### 2. Extract metadata

Record:
- title
- authors
- venue
- year
- paper link
- code link
- dataset link
- artifact link
- project/topic
- reading mode
- reading status

### 3. Read according to mode

#### FAST

Read:
- abstract
- introduction
- conclusion
- method overview
- central theorem/result
- most important evaluation section

Read appendix/details only when needed to verify or understand a central claim.

Stop once the core idea, evidence, and main limitation are clear.

#### DEEP

Read:
- abstract
- introduction
- conclusion
- definitions
- assumptions
- threat model when relevant
- method
- algorithms
- theorem statements
- derivations/proofs when important
- experiments
- figures/tables
- ablations
- limitations
- related work
- relevant appendix

Reconstruct how the motivation leads to the method and whether the evidence supports the claims.

### 4. Evidence artifacts

#### FAST
Keep only the 1–3 most important figures, tables, equations, or algorithms.

#### DEEP
Inventory all central artifacts required to reconstruct the paper's evidence and technical logic.

### 5. Prior work

#### FAST
Use the closest prior work discussed by the paper. Avoid extra web research unless necessary to understand novelty.

#### DEEP
Position the paper carefully against related work and search current sources when needed.

### 6. Critical synthesis

#### FAST
Identify:
- strongest contribution
- most important limitation
- most fragile assumption
- whether the paper deserves deeper reading

#### DEEP
Evaluate:
- correctness
- usefulness
- novelty
- reproducibility
- scope
- deployment cost
- external validity
- whether experiments actually test the stated claim
- whether motivation genuinely leads to the method

Critique must be concrete and evidence-based.

### 7. Write the note in English

All headings and prose must be in English.

Use `references/note-schema.md`.

Preserve standard technical terminology and notation.

Separate:
- author claims
- demonstrated evidence
- reader inference

After `TL;DR`, include a concise `Critical Take`.

### 8. Tracker integration

Valid statuses are exactly:
- 🔴 To read
- 🟡 Review ready
- 🟢 Done

After a FAST or DEEP note is successfully created:
- set status to `🟡 Review ready`
- add the note link
- update both `reading_queue.md` and `data/paper_registry.json`

Only after the user personally confirms they have reviewed/finished the paper:
- set status to `🟢 Done`

Never mark Done merely because an AI note exists.

### 9. Git behavior

After a reading task:
- run `git status --short`
- stage only files touched by the task
- commit locally
- do not push automatically unless the user explicitly authorizes pushing in the current session

Suggested commit messages:
- `Add paper note: <short paper title>`
- `Update paper note: <short paper title>`

If committed locally, tell the user to run `git push`.

## Output Files

Use topic folders such as:
- `notes/privacy/`
- `notes/posterior-sampling/`
- `notes/synthetic-data/`
- `notes/missing-data/`
- `notes/trustworthy-ml/`

Use filenames like:
`【VENUE‘YEAR】short-title.md`

Use the same prefix in the note title.

## Quality Bar

- FAST is the default.
- DEEP overrides FAST whenever explicitly requested.
- Do not silently escalate FAST into DEEP.
- FAST optimizes for decision-useful understanding, not exhaustive coverage.
- DEEP preserves a complete evidence trail when needed.
- Do not overclaim novelty.
- Do not omit material assumptions.
- Critique must be specific and evidence-based.
- Final saved notes must be entirely in English.
