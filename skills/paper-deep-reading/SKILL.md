---
name: paper-deep-reading
description: Deep-read academic papers and produce structured Chinese research notes with critical analysis. Use when the user provides a paper title, DOI, arXiv/publisher/GitHub/PDF URL, local PDF, or asks to 精读, 阅读, 整理, 总结, 复现, 归纳贡献, 分析实验, 批判性分析, 比较相关工作, or maintain a paper-reading repository index.
---

# Paper Deep Reading

## Overview

Use this skill to turn a paper into a durable Chinese research note, not a loose summary. Prioritize factual grounding, explicit uncertainty, and connections to the user's existing paper-reading repository.

For the full note schema, read `references/note-schema.md` when creating or revising a note file.

## Workflow

1. Resolve the paper source.
   - If the user gives a local PDF, read it directly.
   - If the user gives a URL, open or download the paper from that URL.
   - If the user gives only a title, search for an official source first: arXiv, publisher page, author page, DOI, conference page, or project page.
   - When working inside a paper-reading repo, search `README.md`, `notes/`, `papers/`, and `literature/` for existing notes or local copies before creating a new note.
   - Record the source URL and access path in the note.
   - If metadata is uncertain, mark it as `Unknown` or `TBD`; do not invent venue, year, code, dataset, or claims.

2. Extract core metadata.
   - Title, authors, venue, year, paper link, code link, dataset link, artifact link, scope/subfield, topic tags, and reading status.
   - For DeFi papers, set `Scope / Subfield` to the narrow research lane, such as `攻击检测`, `全范围恶意检测`, `攻击溯源`, `价格操纵检测`, `MEV 测量`, `套利检测`, `图方法检测`, or `规则判断检测`.
   - For blockchain/DeFi papers, add tags such as `MEV`, `DEX`, `Oracle`, `Arbitrage`, `Lending`, `Liquidation`, `Stablecoin`, `Cross-chain`, `Rug Pull`, `Formal Methods`, `Measurement`, or `Attack Detection` when supported by the paper.

3. Read in three passes.
   - Pass 1: Abstract, introduction, conclusion. Identify the problem, essential motivation, basic idea, claimed contributions, and main result. Do not stop at surface motivation; distinguish the real pain point, missing capability, broken assumption, or research gap that makes the paper worth doing.
   - Pass 2: Method, threat model, assumptions, algorithms, system design, and definitions. Extract the paper's actual mechanism instead of paraphrasing only at a high level. Reconstruct how the basic idea could be derived from the motivation and then developed into the concrete method.
   - Pass 3: Evaluation, tables, figures, ablations, case studies, limitations, and related work. Check whether the experiments support the claims.

4. Extract evidence artifacts.
   - Inventory the paper's central figures, tables, equations, algorithms, and definitions.
   - Include the artifacts that carry the paper's main claims; if the user asks for exhaustive notes, include every figure, table, and important equation.
   - For formulas and algorithms, preserve the paper's notation and check for variable meaning, ranges, missing operators, and consistency with the surrounding text.
   - For tables and figures, state what each one is evidence for instead of only describing its appearance.

5. Position against prior work.
   - Identify the closest prior work and the paper's claimed delta.
   - Distinguish method novelty, setting novelty, data novelty, and finding novelty.
   - If the delta depends on recent work or post-publication impact, search current sources and cite them.

6. Run a critical synthesis pass.
   - Ask whether the work is convincing, useful, reproducible, and well-scoped.
   - Check the core questions: what problem is being solved, what prior practice failed to handle, what is new, who benefits, what can go wrong, what it costs to reproduce or deploy, and whether the experiments actually test the claim.
   - Check whether the method really follows from the stated motivation, or whether the motivation is mostly post-hoc framing.
   - Use this as an internal analysis pass. Do not create a separate critical-review section in the final note.
   - Convert the judgment into the final note's `Strengths`, `Limitations`, and `My Takeaways` sections.
   - Keep attribution clear in prose when needed: separate what the paper demonstrates from what the reader concludes.
   - Make critique concrete: unsupported threat model, unrealistic DeFi market assumption, incomplete adversary model, weak baseline, narrow dataset, missing ablation, fragile labels, data leakage, post-hoc rules, reproducibility gap, deployment cost, or unclear real-world impact.
   - If evaluating post-publication impact, adoption, or follow-up work, search the web in the same turn and cite the sources used. Do not cite impact from memory.

7. Write the note in Chinese.
   - Use the schema in `references/note-schema.md`.
   - Keep paper terms precise; preserve key English terms in parentheses when translation may lose meaning.
   - Separate the authors' claims from your analysis.
   - Give special attention to `Motivation and Basic Idea`: explain the most fundamental reason the paper exists and the simplest idea the method is built on.
   - Keep `Background` concise: record only the chain from background to problem to gap. Do not write a long textbook-style background section.
   - Treat `Threat Model / Assumptions` as optional. Include it when assumptions materially affect correctness, security, economics, or applicability; otherwise write `N/A` or omit fine detail.
   - In `Method`, analyze how the basic idea becomes the concrete method. Ground this in the paper's text, related work, assumptions, ablations, or system constraints; if the logic is inferred, label it as inference.
   - After `TL;DR`, add a short `毒舌评论`: one sharp paragraph or 2-3 bullets that gives a hard, fact-grounded judgment on the paper's real value, biggest weakness, possible overclaim, or most fragile assumption. It must not be a summary. Make the verdict sting, but do not invent defects or state uncertain criticisms as facts.
   - Keep `Evaluation` focused on experiment idea, evaluation metrics, and results. Include dataset scale, baselines, or key figures only when they are necessary to understand the result.
   - End with connections to prior/future papers and questions worth revisiting.

8. Maintain the repository index when working inside a paper-reading repo.
   - If `README.md` contains a conference index, update the correct venue/year entry.
   - Change status from `TODO` to `DONE` only after a note file exists.
   - Link the index entry to the note file and keep the paper URL accessible.
   - If the venue/year is unknown, add an `Unknown / TBD` section rather than guessing.

9. Sync the completed note to GitHub when working inside a Git-backed paper-reading repository.
   - After the note and index are updated, run `git status --short`.
   - Stage only files touched by this paper-reading task, usually `README.md`, the note under `notes/defi/`, and any intentionally created paper-specific assets.
   - Do not stage unrelated user changes.
   - Commit with `Add paper note: <short paper title>` for a new note or `Update paper note: <short paper title>` for a revision.
   - Push immediately with `git push`.
   - If there are no changes, do not create an empty commit. If push fails, report the error clearly and leave the local commit intact.

## Output Files

When the user wants notes saved in the current repo:

- Place DeFi notes under `notes/defi/`.
- Use filenames like `【VENUE‘YEAR】short-title.md`, such as `【TDSC‘2024】defiranger.md` or `【CCS‘2026】paper-short-title.md`.
- Use the same prefix in the note title: `# 【VENUE‘YEAR】Paper Title`.
- If the venue or year is unknown, use `【TBD】short-title.md`.
- Prefer editing an existing note over creating duplicates for the same paper.

## Quality Bar

- Do not rely on abstract-only summaries unless the paper cannot be accessed; state that limitation clearly.
- The `毒舌评论` must be meaningfully sharper than the TL;DR. If it could be mistaken for a neutral summary, rewrite it.
- Do not overclaim novelty; describe novelty as the paper frames it and compare to related work when available.
- Do not omit assumptions. For security, DeFi, and blockchain papers, assumptions often determine whether the result is meaningful.
- Preserve equations, algorithms, and important definitions when they are central to the paper.
- Preserve the evidence trail: key figures, tables, datasets, metrics, and ablations should be traceable to the claims they support.
- Prefer specific critique: unsupported threat model, weak baseline, narrow dataset, missing ablation, unrealistic market assumption, or external validity issue.
