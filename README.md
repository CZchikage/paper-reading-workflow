# Paper Reading Workflow

A reusable Codex workflow for deep-reading academic papers and maintaining a Git-backed paper note repository.

The current default profile is optimized for blockchain and DeFi papers, but the workflow is intentionally lightweight: one Codex skill, one `.agent` workflow file, and one example note.

## What It Does

- Turns a paper title, URL, DOI, arXiv link, publisher page, GitHub artifact, or local PDF into a structured Chinese deep-reading note.
- Emphasizes motivation, basic idea, method reasoning, evidence, limitations, and personal takeaways.
- Adds a sharp fact-grounded `毒舌评论` after the TL;DR.
- Keeps background concise: background -> problem -> gap.
- Keeps evaluation focused: experiment idea, metrics, results.
- Updates the repository paper index when applicable.
- Commits and pushes the generated note to GitHub after each completed reading task.

## Repository Layout

```text
.
├── .agent
├── LICENSE
├── README.md
├── examples/
│   └── defiranger-note.md
└── skills/
    └── paper-deep-reading/
        ├── SKILL.md
        ├── agents/
        │   └── openai.yaml
        └── references/
            └── note-schema.md
```

## Install

Install the Codex skill locally:

```bash
mkdir -p ~/.codex/skills
cp -R skills/paper-deep-reading ~/.codex/skills/
```

To use the workflow in a paper-reading repository, copy `.agent` into that repository root:

```bash
cp .agent /path/to/your-paper-reading-repo/.agent
```

The target repository should usually contain:

```text
README.md
notes/
```

For the default DeFi workflow, notes are written under:

```text
notes/defi/
```

## Usage

Ask Codex to read a paper:

```text
精读这篇论文：https://arxiv.org/abs/xxxx.xxxxx
```

```text
读一下 /path/to/paper.pdf，并整理到 notes/defi/
```

```text
精读 DeFiRanger: Detecting DeFi Price Manipulation Attacks
```

After the note is generated, the workflow stages only the files touched by the paper-reading task, commits them, and runs `git push`.

## Note Style

The note schema lives in:

[skills/paper-deep-reading/references/note-schema.md](skills/paper-deep-reading/references/note-schema.md)

The main sections are:

- Metadata
- TL;DR
- 毒舌评论
- Research Question
- Motivation and Basic Idea
- Background
- Threat Model / Assumptions (optional)
- Method
- Evaluation
- Key Artifacts
- Findings
- Strengths
- Limitations
- My Takeaways
- Related Papers
- Open Questions

See [examples/defiranger-note.md](examples/defiranger-note.md) for a complete example.

## Git Sync Policy

The workflow is conservative about Git operations:

- Stage only files touched by the current paper-reading task.
- Do not stage unrelated user changes.
- Do not create empty commits.
- Push immediately after a successful commit.
- If push fails, leave the local commit intact and report the error.

## License

MIT
