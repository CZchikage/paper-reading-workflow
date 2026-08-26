# Paper Reading Workflow — Auto Discovery v2

Drop these files into a fork of `LazyDreamingDog/paper-reading-workflow`.

## v2 additions

### 1. Multi-source discovery
- arXiv
- Semantic Scholar
- OpenReview

A source can fail without blocking the entire weekly refresh.

### 2. Better ranking
Transparent relevance score combines:
- research-topic matches
- extra weight for title matches
- theory / sub-Gaussian / Bayesian / tabular bonuses
- venue bonuses
- small recency bonus

### 3. Weekly shortlist
`reading_queue.md` now has:
- **This Week — Must Read**: default top 5
- **Full Ranked Queue**: default top 20
- priorities: 🔴 / 🟠 / 🟡 / 👀

### 4. State preservation
Refreshes preserve manual edits to:
- Status
- Project
- Notes

So GitHub Actions will not wipe your reading progress every Monday.

### 5. LaTeX integration
Every discovered paper gets a deterministic BibTeX key such as:

`smith2026posterior`

and the current shortlist is exported to:

`bib/discovered.bib`

You can `\cite{...}` immediately or copy selected entries into a project-specific `.bib`.

### 6. Automatic weekly refresh
`.github/workflows/discover-papers.yml` runs every Monday at 13:00 UTC.
During US daylight-saving time that is 08:00 Chicago; during standard time it is 07:00.
GitHub cron itself has no timezone support.

## Install
Copy the files into your fork, preserving paths, then run:

```bash
python scripts/discover_papers.py
```

or use **Actions → Discover latest papers → Run workflow**.

## Tune your research profile
Edit:

`config/paper_discovery.json`

The defaults focus on:
- differential privacy
- posterior sampling / Bayesian inference
- synthetic data
- trustworthy ML
- missing data / imputation

## Important
The auto-generated `bib/discovered.bib` is intentionally a staging bibliography.
For final manuscripts, keep a curated project bibliography rather than blindly citing every discovered record.
