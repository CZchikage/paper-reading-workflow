---
name: paper-discovery
description: Discover, rank, shortlist, and route recent research papers into the paper-reading workflow.
---

# Paper Discovery

## Goals
Maintain a small, high-quality reading queue rather than a large undifferentiated feed.

## Discovery
1. Read `config/paper_discovery.json`.
2. Run `python scripts/discover_papers.py`.
3. Inspect `reading_queue.md`.
4. Prefer the `This Week — Must Read` section for active reading.
5. Do not deep-read every discovered paper automatically.
6. When the user selects a paper, pass it to `paper-deep-reading`.
7. After a note is created, mark the queue item `DONE`.

## Ranking
The score is transparent:
- topic keyword match
- stronger title-match weight
- theory/sub-Gaussian/Bayesian/etc. bonuses
- venue bonuses
- slight recency bonus

## LaTeX / BibTeX
The discovery script generates `bib/discovered.bib`.
Use the shown citation key when the paper is cited in LaTeX.
The file is a convenience layer, not a replacement for a curated project bibliography.

## State preservation
Automated refreshes preserve manually edited `Status`, `Project`, and `Notes` cells for papers already present in the queue.

## Sources
- arXiv
- Semantic Scholar
- OpenReview

All are queried without paid credentials. Individual public endpoints may occasionally rate-limit; source failures are non-fatal.
