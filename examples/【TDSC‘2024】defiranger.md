# 【TDSC‘2024】DeFiRanger: Detecting DeFi Price Manipulation Attacks

## Metadata

- Title: DeFiRanger: Detecting DeFi Price Manipulation Attacks
- Authors: Siwei Wu, Zhou Yu, Dabao Wang, Yajin Zhou, Lei Wu, Haoyu Wang, Xingliang Yuan
- Venue / Year: IEEE Transactions on Dependable and Secure Computing, 21(4), 2024
- Note Name: 【TDSC‘2024】defiranger
- Paper: https://doi.org/10.1109/TDSC.2023.3346888
- Local PDF: `/Users/wenkuanxiao/Zotero/storage/JHHRMJGG/Wu 等 - 2024 - DeFiRanger Detecting DeFi Price Manipulation Attacks.pdf`
- Code: Unknown. 论文只说明实现了约 6,140 行 Rust 原型，没有在 PDF 中给出公开仓库。
- Dataset / Artifact: IEEE DOI 页面提供 supplementary material；论文主体未给出可直接复现实验数据集。
- Scope / Subfield: 价格操纵检测
- Tags: DeFi, DEX, AMM, Oracle, Flash Loan, Attack Detection, Transaction Analysis, Rule-based Detection
- Status: DONE

## TL;DR

这篇论文做的是链上 DeFi 价格操纵攻击检测：先把原始 EVM 交易 trace 恢复成 Cash Flow Tree (CFT)，再从 transfer/mint/burn 等低级动作提升出 trade、deposit、withdrawal、borrowing、repayment 等高层 DeFi 语义，最后用基于语义的攻击模式检测 Type I 和 Type II 价格操纵。最终版本在 15,272 笔交易、8,117 个高级动作的人工标注集上达到语义恢复 precision 0.996、TPR 0.962；实际部署发现 14 个 zero-day 事件，回测 92,325,423 笔 EVM 交易时检测到 129 个真攻击、26 个误报，precision 0.832。它的价值不在“规则检测”本身，而在把交易级低层日志提升为可表达 DeFi 攻击模式的中间语义层。

## 毒舌评论

DeFiRanger 最硬的贡献是把“看不懂交易 trace”这个脏活做成了可复用的语义恢复流程；但它的检测边界也很直白：攻击必须落进作者预先总结的 hoard-and-dump 模式，且最好发生在单笔 EVM transaction 内。换句话说，它很会抓作者已经抽象清楚的那类价格操纵，但对跨交易、非标准 token、内部账本缺少外部信息、以及未来变体的鲁棒性并不神奇。论文的工程含金量高于算法新意。

## Research Question

- 研究对象：DeFi 交易中的价格操纵攻击，尤其是 DEX、借贷和收益聚合协议之间的组合式攻击。
- 小领域范围：交易 trace 语义恢复 + 链上攻击检测。
- 具体问题：如何从原始 EVM transaction / internal transaction / event 中恢复 DeFi 语义，并用这些语义检测真实世界价格操纵攻击。
- 为什么重要：传统智能合约工具主要看 reentrancy、integer overflow 等代码级漏洞，无法直接理解“某账户在某 DEX 池中买入、拉价、抵押、借出、反向卖出”这样的协议级经济行为。
- 论文边界：只考虑单个 raw transaction 中可恢复的动作；不覆盖 NFT；检测依赖 ERC20 Transfer 事件、外部信息库和预定义攻击模式。

## Motivation and Basic Idea

- Motivation：价格操纵攻击是协议层经济漏洞，不是单个函数里的典型代码漏洞。检测这种攻击需要知道攻击者是否完成了 trade、deposit、borrow、withdraw 等 DeFi 级行为，但链上可直接看到的只是调用、事件和 token transfer。
- Basic idea：把交易 trace 建成 Cash Flow Tree，再把低级资金流动作逐步提升为高级 DeFi actions；攻击检测规则不直接写在 raw trace 上，而写在恢复出的 DeFi semantics 上。
- 这个 idea 如何回应 motivation：如果能稳定恢复“攻击者先在 DEX 中买入/拉价，再利用受害协议按被操纵价格结算，最后卖出/借出获利”这种语义链，那么价格操纵检测就可以从 brittle 的合约特例规则转成协议级行为模式。
- 作者给出的证据：手工构造高级 DeFi action ground truth，部署系统发现 zero-day，回测大规模交易并分析误报原因。
- 我的判断：语义提升是这篇的关键抽象。攻击 pattern 仍是规则，但规则作用在高层语义上，比直接从 transaction 字段硬凑模式更可维护。

## Background

- 背景：AMM DEX 用池子 reserve 计算价格，借贷/收益协议常依赖 DEX quote、reserve、LP token supply 或外部 token supply 估值。
- 问题：flash loan 让攻击者能在单笔交易中临时获得大资金，操纵 DEX 价格后诱导受害协议以错误价格交易、铸币、赎回或借贷。
- Gap：现有代码级工具不理解 DeFi 行为语义；profit-based 工具会混入套利和清算，攻击精度不足。

## Threat Model / Assumptions

- 攻击者或参与者能力：攻击者可发起 EVM transaction、使用 flash loan、调用公开接口、操纵 DEX 池子 reserve 或 token supply。
- 链上 / 链下假设：系统输入是 raw transaction 的 invocation trace、events 和基础转账信息；需要能获得 internal transaction 执行关系。
- 市场、流动性、排序、预言机或网络假设：攻击通常在单笔 EVM transaction 中完成，以避免被外部套利修正；Type II 常依赖受害协议使用 DEX 实时价格或实时 reserve。
- 不覆盖的情况：跨 transaction 攻击、非 ERC20 Transfer 标准 token、没有外部信息支持的内部账本协议、未来不符合既有 patterns 的攻击变体。

## Method

- 核心思路：CFT construction -> semantics lifting -> attack detection。
- 核心思路是怎么想到的：攻击检测需要 trade/deposit/borrow 等高层动作；这些动作本质上由 transfer/mint/burn 组成，所以可以从资金流和调用树恢复。
- 从 motivation 到 method 的逻辑链：raw trace 不够语义化 -> 定义基础和高级 DeFi actions -> 构造保留调用/事件/转账上下文的 CFT -> 用 connection、insertion、combination 从低级动作组合高级动作 -> 用高层动作 pattern 检测攻击。
- 关键设计取舍：论文没有尝试理解每个 DeFi 协议的业务代码，而是抽象出通用资金流语义；但对内部账本场景仍需要手工外部信息，这削弱了“平台无关”的完全性。
- 为什么不是更直接 / 更简单的方案：直接匹配 Transfer 序列容易误把跨合约转账识别成冗余 trade，也无法识别内部账本里的隐式 token flow；直接找 profit 又会把套利/清算混进攻击。
- 系统流程或算法步骤：
  - CFT construction：输入 invocation trace，构造 invocation node、event node、basic node；native token transfer 从 value 字段得到，ERC20 transfer 从 Transfer event 得到。
  - Semantics lifting：按 post-order 遍历所有 subtree，依次做 connection、insertion、combination。
  - Connection：对相同 token 的基础动作建立连接而不是合并，用 `remains_in` / `remains_out` 跟踪尚未流入/流出的数量，避免把中间合约转账误识别成冗余 trade。
  - Insertion：对维护 internal ledger 的合约，手工提供 `sig_f`、`sig_e`、`loc_spender`、`loc_recipient`、`loc_token`、`loc_amount`，从函数/事件参数补出内部 basic action。
  - Combination：用表 VI 的组合规则从基础动作推导 trade、borrowing、repayment、depositing、withdrawal 等高级动作；再把 depositing + borrowing 抽象为 collateral borrowing。
  - Attack detection：先检测 hoard-and-dump 候选，再用八类 pattern 判断 Type I / Type II 价格操纵。
- 关键定义 / 公式 / 不变量：
  - Basic actions：Transfer `T(spender, recipient, amount, token)`，Minting `M(recipient, amount, token)`，Burning `B(spender, amount, token)`。
  - Advanced actions：Trade `Tr(T_in, T_out)`；Depositing `De(Ts, M_share)`；Withdrawal `Wi(Ts, B_share)`；Borrowing `Bo(Ba_T/M, M_debt)`；Repayment `Re(Ba_T/B, B_debt)`；Collateral Borrowing `Cb(De, Bos)`。
  - AMM 简化公式：`xy = c`，`Delta y = Delta x * y / (Delta x + x)`，价格可被大额交易改变。
  - Price dependency 公式：Harvest 类协议依赖 `R_USDC + ToUSDC(R_yCrv)`；LP 抵押类协议依赖实时 reserve 和 LP total supply；Array Finance 依赖外部 token total supply。
- 实现细节：原型名为 DEFIRANGER，约 6,140 行 Rust；真实部署与 BlockSec 合作，覆盖 Ethereum 和 BSC 中的事件。

## Evaluation

- 实验思路：分两部分评估：一是高级 DeFi 语义恢复是否准确，二是攻击检测是否能在真实部署和历史回测中发现攻击。
- 评估指标：语义恢复使用 TP/FP/FN、precision、TPR；攻击检测主要报告真攻击、误报、precision，并结合 zero-day 和 unknown historical incidents 评估实用性。
- 主要结果：
  - 语义恢复：人工抽取 2022-10-07 08:00-09:00 UTC 的 Ethereum 数据，得到 15,272 笔交易、8,117 个高级 DeFi actions。DEFIRANGER 识别 7,841 个，其中 7,808 TP、33 FP、309 FN，precision 0.996，TPR 0.962。
  - 真实部署：从 2020 年中到 2023-04-29 与 BlockSec 做实时检测，发现 14 个 zero-day security incidents。
  - 回测：收集 26 个已知价格操纵事件对应日期的交易，共 92,325,423 笔 EVM transactions，其中 Ethereum 13,611,237，BSC 78,714,186。系统标记 155 笔攻击，129 TP、26 FP，precision 0.832。
  - 未知历史攻击：除 26 个已知事件外，人工确认 15 个社区未公开标注的 historical incidents。
  - 误报来源：transfer fee token 触发 Pattern II 17 个误报；DEX trade fee transfer 触发 Pattern II 5 个误报；buyback design 触发 Pattern I/III 4 个误报。

## Key Artifacts

- 关键图：
  - Fig. 1：raw transaction 包含 external transaction 与 internal transaction，说明系统输入粒度。
  - Fig. 2：inter-contract token transfers，解释为什么“合并同 token transfer”会漏掉 yield farming -> DEX 的嵌套 deposit，而 connection 更合适。
  - Fig. 3：系统 workflow：EVM transaction trace -> CFT Construction -> Semantics Lifting -> Attack Detection。
  - Fig. 4：完整示例，展示 insertion、connection、combination 如何把基础节点提升为 `Tr`、`De`、`Bo`，最后匹配 Type II pattern。
- 关键表：
  - Table I/II：基础动作和高级动作定义，是全文语义层的核心接口。
  - Table IV-VI：basic action identification、connection、combination 规则，构成语义恢复算法主体。
  - Table VII/VIII：collateral borrowing 和 hoard-and-dump 检测规则，连接语义恢复与攻击检测。
  - Table IX：八类价格操纵攻击 pattern；Pattern I-IV 属 Type I，Pattern V-VIII 属 Type II。
  - Table X：真实事件列表，包括 bZx、Balancer、Loopring、Harvest、Cheese Bank、Value DeFi、Warp Finance、Belt、Array 等，以及 15 个 unknown historical attacks。
- 关键公式 / 定义 / 算法：
  - AMM reserve pricing 说明价格操纵的经济前提。
  - BackTrack / Trace 思路用于比较 hoard 成本 token 和 dump 收益 token，即使中间经过不同 token。
  - `Adv | contract` / `Adv | token` 依赖关系用于判断某高级动作是否依赖特定合约状态或 token balance / total supply。
- 这些证据分别支撑哪些结论：动作定义和规则支撑“可恢复 DeFi 语义”；Table X 和部署结果支撑“能发现真实攻击”；误报/漏报分析支撑“规则方法有效但边界明确”。

## Findings

- 发现 1：价格操纵检测的关键不是某个单独 Transfer，而是恢复出 hoard -> manipulate/use victim -> dump/borrow/redeem 的高层语义链。
- 发现 2：真实攻击根因可归到四类：access control、design compatibility、slippage check、price dependency。前三类主要导致 Type I，price dependency 主要导致 Type II。
- 发现 3：内部账本和非标准 token 是语义恢复最脆的地方；这类协议越“自定义”，通用资金流抽象越需要外部补丁。

## Strengths

- 论文最有说服力的地方：把 DeFi 交易理解问题拆成可操作的语义层，并且给出真实部署与回测证据。
- 方法、数据、实验或问题设定的优势：不是只在少数案例上手写规则，而是先定义通用 DeFi actions，再用统一模式表达多类攻击。
- 相比已有工作的有效推进：比 smart contract vulnerability tools 更接近协议层经济行为；比 profit-based tools 更能区分攻击与普通套利/清算。

## Limitations

- 威胁模型、假设或适用范围的限制：只检测单笔 EVM transaction 内的攻击；跨 transaction 价格操纵无法覆盖。
- 数据集、baseline、metric、ablation 或复现性的不足：代码和完整 artifact 不公开，supplementary material 需要通过 IEEE DOI 获取；语义 ground truth 是作者人工构造，复核成本高。
- 在真实 DeFi 场景中可能失效的条件：缺少某些 DeFi app 的 external information 会产生 FN；非 ERC20 标准 token 可能导致 basic action 漏识别；未来不符合现有 hoard-and-dump pattern 的变体可能绕过。

## My Takeaways

- 对 DeFi / 区块链安全研究的启发：协议层攻击检测需要中间语义表示；直接在 trace 上写规则可迁移性太差。
- 可复用的方法：CFT + semantics lifting 可以作为 DeFi 交易理解的基础设施，用于攻击检测、解释、分类和事后取证。
- 可能的后续问题：如何减少手工 external information？如何覆盖跨 transaction 策略？如何把 rule-based pattern 与 anomaly/profit/LLM reasoning 结合，而不牺牲可解释性？

## Related Papers

- 前置阅读：Flash Boys 2.0；High-Frequency Trading on Decentralized On-Chain Exchanges；Attacking the DeFi Ecosystem with Flash Loans for Fun and Profit；SoK: Decentralized Finance (DeFi) Attacks。
- 后续阅读：DeFiTainter；DeFort；DeFiGuard；DeFiScope；Following Devils' Footprint。
- 可对比论文：TXSPECTOR / EthScope 偏交易级攻击检测但不是 DeFi price manipulation semantics；DeFiPoser / APE 偏 profit-generating transaction，容易混入套利和清算。
- 最接近的相关工作：DeFiPoser、APE、SoK: DeFi Attacks。
- 关键差异：DeFiRanger 不是用收益最大化或纯交易 profit 来找攻击，而是先恢复 DeFi actions，再用语义 pattern 判断攻击。

## Open Questions

- 语义恢复能否学习化，但仍保留 Table I/II 这种可审计接口？
- 对 custom pricing model，CFT action semantics 是否足够，还是必须理解协议源码中的价格函数？
- 如果攻击被拆成多笔交易，应该如何把跨 transaction 状态依赖合并成攻击 graph？
- 误报中的 fee-on-transfer、buyback、trade fee 机制能否自动识别为 tokenomics feature，而不是攻击 pattern？
