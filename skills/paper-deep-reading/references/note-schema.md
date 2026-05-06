# Deep Reading Note Schema

Use this schema when creating or revising a paper note. Keep headings stable so notes remain comparable across papers.

```markdown
# Paper Title

## Metadata

- Title:
- Authors:
- Venue / Year:
- Paper:
- Code:
- Dataset / Artifact:
- Scope / Subfield:
- Tags:
- Status: DONE

## TL;DR

用 2-4 句话说明：论文解决的问题、核心方法、最重要结论、为什么对当前研究线有价值。

## 毒舌评论

用一小段话或 2-3 个 bullet 给出够狠的直接判断：这篇论文到底有多大价值、最可能被高估的地方是什么、最大短板或最脆弱假设在哪里。不能写成摘要，必须比 TL;DR 更尖锐；但每个狠话都要有论文事实支撑，不确定就明确说“不确定”。

## Research Question

- 研究对象：
- 小领域范围：
- 具体问题：
- 为什么重要：
- 论文边界：

## Motivation and Basic Idea

- Motivation：
- Basic idea：
- 这个 idea 如何回应 motivation：
- 作者给出的证据：
- 我的判断：

## Background

- 背景：
- 问题：
- Gap：

## Threat Model / Assumptions (Optional)

- 攻击者或参与者能力：
- 链上 / 链下假设：
- 市场、流动性、排序、预言机或网络假设：
- 不覆盖的情况：

## Method

- 核心思路：
- 核心思路是怎么想到的：
- 从 motivation 到 method 的逻辑链：
- 关键设计取舍：
- 为什么不是更直接 / 更简单的方案：
- 系统流程或算法步骤：
- 关键定义 / 公式 / 不变量：
- 实现细节：

## Evaluation

- 实验思路：
- 评估指标：
- 主要结果：

## Key Artifacts

- 关键图：
- 关键表：
- 关键公式 / 定义 / 算法：
- 这些证据分别支撑哪些结论：

## Findings

- 发现 1：
- 发现 2：
- 发现 3：

## Strengths

- 论文最有说服力的地方：
- 方法、数据、实验或问题设定的优势：
- 相比已有工作的有效推进：

## Limitations

- 威胁模型、假设或适用范围的限制：
- 数据集、baseline、metric、ablation 或复现性的不足：
- 在真实 DeFi 场景中可能失效的条件：

## My Takeaways

- 对 DeFi / 区块链安全研究的启发：
- 可复用的方法：
- 可能的后续问题：

## Related Papers

- 前置阅读：
- 后续阅读：
- 可对比论文：
- 最接近的相关工作：
- 关键差异：

## Open Questions

- 
```

If a section does not apply, keep the heading and write `N/A` or `TBD` with a short reason.

For DeFi papers, `Scope / Subfield` should capture the paper's narrow research lane, not every keyword. Examples: `攻击检测`, `全范围恶意检测`, `攻击溯源`, `价格操纵检测`, `MEV 测量`, `套利检测`, `Rug Pull 检测`, `图方法检测`, `规则判断检测`, `形式化验证`, `经济安全分析`, `借贷清算风险`, `跨链攻击分析`.

Use an internal critical analysis step: goal, prior practice, novelty, impact, risks, cost, and evidence. Do not add a separate critical-review section. Convert that judgment into `Strengths`, `Limitations`, and `My Takeaways`. When judging external impact or follow-up work, use sources retrieved in the current turn instead of memory.

When filling `Key Artifacts`, prefer the figures, tables, equations, algorithms, and definitions that carry the paper's core claims. Preserve notation accurately and explain what each artifact proves. If the user requests exhaustive notes, include every figure, table, and important equation.
