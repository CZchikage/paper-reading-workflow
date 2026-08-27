# 【NeurIPS‘2024】ClavaDDPM: Multi-relational Data Synthesis with Cluster-guided Diffusion Models

## Metadata

- **Title:** ClavaDDPM: Multi-relational Data Synthesis with Cluster-guided Diffusion Models
- **Authors:** Wei Pang, Masoumeh Shafieinejad, Lucy Liu, Stephanie Hazlewood, Xi He
- **Venue:** 38th Conference on Neural Information Processing Systems (NeurIPS)
- **Year:** 2024
- **Paper:** [NeurIPS abstract page](https://proceedings.neurips.cc/paper_files/paper/2024/hash/983876577ec81db17ecfae1521df9208-Abstract-Conference.html) · [Official PDF](https://proceedings.neurips.cc/paper_files/paper/2024/file/983876577ec81db17ecfae1521df9208-Paper-Conference.pdf) · DOI: `10.52202/079017-2657`
- **Code:** Unknown; the official PDF does not provide a public repository link.
- **Dataset:** California, Instacart 05, Berka, MovieLens, and CCS multi-relational datasets
- **Artifacts:** Dataset statistics, implementation details, algorithms, ablations, high-order utility evaluation, and a DCR privacy sanity check are included in the appendix.
- **Project / Topic:** Multi-relational synthetic data; tabular diffusion models; foreign-key dependency modeling
- **Reading Mode:** FAST
- **Status:** 🟡 Review ready

## TL;DR

ClavaDDPM synthesizes an entire relational database rather than generating each table independently or flattening all tables into one denormalized relation. Its key device is a discrete cluster latent variable that summarizes the relationship between a parent row and its foreign-key child group. Diffusion models generate augmented parent tables, classifier guidance generates child rows conditioned on the propagated cluster labels, and approximate nearest-neighbor matching reconciles child tables with multiple parents. Across five databases, the method is particularly strong at preserving multi-hop column dependencies and completes all reported experiments within two days, while several baselines fail to converge or exceed the seven-day limit.

## Critical Take

The paper solves an important representational problem: how to give a row-wise tabular generator enough context to reproduce database-wide dependencies without conditioning directly on thousands of parent identities. The clustering proxy is effective but also the method's most fragile point—it assumes a coarse discrete label captures the parent–child dependence that matters. More importantly, despite privacy appearing in the motivation and tracker tags, ClavaDDPM is not differentially private. Its DCR comparison with SMOTE is only a weak memorization sanity check and should not be interpreted as a privacy guarantee.

## Research Question

How can diffusion models synthesize a database containing multiple foreign-key-linked tables while remaining scalable and preserving intra-table, within-group, one-hop, and long-range inter-table dependencies?

## Motivation and Basic Idea

Single-table generators ignore relational structure. Generating each table separately preserves marginal distributions but breaks correlations across foreign keys. Joining everything into one table becomes inefficient and duplicates parent information, while prior relational synthesizers such as SDV and PrivLava can struggle with large attribute domains, complex schemas, or many tables.

ClavaDDPM replaces direct conditioning on a high-dimensional parent row with conditioning on a learned cluster label. For a parent row $y_j$ and its variable-sized child group $g_j$, it introduces a latent $c$ intended to make the two conditionally independent. The child-group size and child rows are then generated conditional on $c$. Because the label space is compact, classifier-guided diffusion can model it more reliably than thousands of parent identities.

## Background

A relational database is represented as a directed acyclic graph whose nodes are tables and whose edges are foreign-key references from child to parent. High-quality synthesis must preserve more than individual columns: it must also reproduce group cardinalities, dependencies among children sharing a parent, and correlations between columns separated by several table hops. Existing single-table metrics therefore miss the main failure mode of relational synthesis.

## Main Contributions

- **Modeling:** Formulates relational synthesis using foreign-key groups and a cluster latent variable that mediates parent–child dependencies.
- **Architecture:** Combines a unified Gaussian tabular diffusion backbone with classifier-guided conditional sampling.
- **Schema handling:** Propagates latent labels bottom-up during learning and generates tables top-down; uses approximate nearest-neighbor matching for children with multiple parents.
- **Evaluation:** Establishes a five-database benchmark and introduces $k$-hop column correlations as an explicit measure of long-range relational fidelity.
- **Empirical result:** Substantially improves multi-hop dependency scores while remaining competitive on marginal, cardinality, and single-table utility metrics.

## Method

For a two-table database, let $y_j$ be a parent row and $g_j=\{x_j^1,\ldots,x_j^{s_j}\}$ its child group. The paper approximates the database distribution by independent parent-group pairs and introduces a cluster label $c$ such that $g_j$ and $y_j$ are conditionally independent given $c$. The resulting factorization is

$$
p(X,Y)\approx
\prod_j\sum_c
p(y_j,c)\,p(s_j\mid c)
\prod_{i=1}^{s_j}p(x_j^i\mid c).
$$

The pipeline has three stages:

1. **Relationship-aware clustering:** Fit a diagonal-covariance GMM in the weighted joint space $(X;\lambda Y)$. Child rows in a foreign-key group vote on a single cluster label, which is appended to the parent table.
2. **Training:** Train Gaussian diffusion models for the augmented parent table and child table, a noisy-data classifier for cluster labels, and an empirical group-size distribution $p(s\mid c)$.
3. **Synthesis:** Generate parent rows with cluster labels, sample a child-group size for each label, and use classifier guidance to generate the required child rows.

For deeper schemas, latent labels are learned bottom-up so that a table already contains information from its descendants before it augments its parent. Synthesis proceeds in the reverse, top-down order. When a child has several parents, the method independently generates candidate child tables under each parent condition and reconciles nearby candidates through approximate nearest-neighbor matching and interpolation.

## Key Theorems / Results

### Result 1: Latent relational factorization

- **Statement:** Under the paper's conditional-independence assumptions, a parent table and its variable-sized child groups can be approximated by $p(y,c)$, $p(s\mid c)$, and row-wise $p(x\mid c)$ components.
- **Assumptions:** Parent rows are i.i.d.; parent-group pairs are i.i.d.; child groups for different parents are conditionally independent; group size and child rows are conditionally independent given $c$; child rows are i.i.d. given $c$.
- **Interpretation:** The cluster label converts a variable-sized, high-dimensional conditioning problem into ordinary row generation plus conditional cardinality generation.
- **Why it matters:** This factorization is the conceptual foundation of the entire system, although the paper does not provide a theorem establishing approximation error.

### Result 2: Long-range dependency preservation

- **Statement:** In Table 1, ClavaDDPM improves over the best reported baseline by 58.29% on Instacart's 2-hop correlations and by 20.24% on Berka's 3-hop correlations.
- **Assumptions:** Results use the paper's five public datasets, complement-to-KS/TV correlation metrics, three synthetic samples, and the reported hyperparameter settings.
- **Interpretation:** The hierarchical latent propagation captures information beyond adjacent parent–child pairs.
- **Why it matters:** Long-range dependence is the main capability that independent-table and pairwise-denormalization pipelines lack.

### Result 3: Scalability and robustness

- **Statement:** ClavaDDPM completes every reported experiment within two days. PrivLava does not converge on four of five datasets, SDV fails on complex cases, and some TabDDPM pipelines exceed the seven-day limit.
- **Assumptions:** Experiments use one NVIDIA A6000 GPU, 32 CPU cores, and a seven-day cutoff.
- **Interpretation:** Decomposing the schema into conditional table generators scales better than global or repeated denormalized modeling in these experiments.
- **Why it matters:** Multi-table synthesis is useful only if it can handle schemas more complex than two small relations.

## Threat Model / Assumptions

There is no formal privacy threat model and no differential privacy guarantee.

The generative model assumes:

- The foreign-key schema is known and forms a DAG.
- Each primary key is a single identifier attribute and keys themselves are not modeled as ordinary features.
- Parent rows and parent-group pairs can be approximated as i.i.d.
- Child rows from different foreign-key groups are conditionally independent given their parents.
- A discrete cluster label can adequately mediate the parent–child dependence.
- Child rows and group size are conditionally independent given the cluster label.

The appendix reports Distance to Closest Record (DCR) against SMOTE, but DCR does not model an adversary or bound membership/attribute inference risk.

## Evaluation

### Setup

- **Datasets:** California, Instacart 05, Berka, MovieLens, and CCS, spanning simple two-table structures through multi-parent, multi-child schemas.
- **Baselines:** PrivLava, SDV, independent-table pipelines using CTGAN or TabDDPM, and parent–child denormalization pipelines using the same backbones.
- **Metrics:** Foreign-key group cardinality; one-way column density; 0-, 1-, 2-, and 3-hop pairwise column correlations; average two-way utility; appendix metrics include precision/recall, C2ST, machine-learning efficacy, and DCR.
- **Protocol:** Scores are complements of KS distance for numerical values and TV distance for categorical values, averaged over three synthetic datasets.

### Main Findings

- ClavaDDPM has the best average two-way score on all five datasets in Table 1 and its advantage generally grows with hop distance.
- On Berka, the full model reaches 87.27 for 3-hop correlation, compared with 75.56 for the strongest listed baseline; removing multi-parent matching lowers the score to 74.78.
- Setting classifier guidance strength $\eta=0$ slightly improves one-way density but substantially reduces multi-hop correlations, confirming a real fidelity-versus-conditioning tradeoff.
- One cluster ($k=1$) gives perfect within-group label agreement but much worse relational utility; direct-like conditioning with $k=1000$ is also inferior to the default $k=20$ on Berka.
- ClavaDDPM's median DCR is higher than SMOTE's on four selected tables, but this is only a limited privacy sanity check.

## Key Figures / Tables / Equations

### Equation 10: Relational factorization

- **What it shows:** How parent generation, group-size generation, and conditional child generation combine through the cluster label.
- **What claim it supports:** A variable-sized foreign-key group can be synthesized with ordinary row-wise diffusion models after introducing a compact intermediary.
- **Important caveat:** The factorization depends on several unverified conditional-independence approximations.

### Table 1: End-to-end benchmark

- **What it shows:** Marginal, cardinality, and $k$-hop dependency scores for nine baselines/configurations and ClavaDDPM.
- **What claim it supports:** ClavaDDPM's main advantage is long-range relational fidelity and robust completion on complex schemas.
- **Important caveat:** Only three generated datasets are averaged, and the benchmark contains five databases.

### Table 2: Ablation study

- **What it shows:** Effects of cluster count $k$, parent weight $\lambda$, classifier guidance $\eta$, and multi-parent matching.
- **What claim it supports:** Clustering, classifier conditioning, and matching each contribute to multi-hop performance.
- **Important caveat:** The full ablation is conducted only on Berka.

## Strengths

- Identifies long-range inter-table dependence as the correct target instead of relying only on single-table fidelity.
- Provides a coherent mechanism for variable group sizes, deep schemas, and multi-parent children.
- Uses shared backbones in the SingleT and Denorm comparisons, helping separate the relational framework from the base generator.
- Reports failure-to-converge and time-limit outcomes rather than silently excluding weak baselines.
- The ablations directly test the major design elements and expose the conditioning-versus-marginal-fidelity tradeoff.

## Limitations

- No formal privacy guarantee; DCR versus SMOTE is insufficient evidence for privacy-sensitive deployment.
- The cluster label is a lossy bottleneck, and there is no bound on how much relational information the GMM quantization discards.
- Conditional-independence and i.i.d. assumptions may fail for temporal databases, networks, repeated entities, or group-level interactions not explained by the parent.
- Only foreign-key constraints are modeled; denial constraints, business rules, and other integrity constraints are left to future work.
- Label-encoding categorical variables into a Gaussian space imposes an artificial numerical geometry on unordered categories.
- Multi-parent matching is heuristic: proximity between independently generated candidates does not prove sampling from the true joint conditional distribution.
- The main benchmark uses five datasets and three synthetic repetitions, while the comprehensive ablation is limited to one dataset.

## My Takeaways

- In relational synthesis, a useful latent variable must summarize a group-level relationship, not merely compress individual rows.
- Bottom-up context propagation followed by top-down generation is a reusable pattern for DAG-structured data.
- Evaluation should report correlation quality by schema distance; good one-table marginals can conceal complete failure at two or three hops.
- Comparing a full relational method with independent and denormalized pipelines using the same backbone is a strong experimental design.
- Privacy motivation must be separated from privacy evidence: synthetic-looking records and large nearest-neighbor distances do not imply DP.

## What Deserves Deeper Reading

- Appendix B's end-to-end algorithms for bottom-up training and top-down synthesis.
- The exact multi-parent matching and interpolation procedure, especially its behavior for more than two parents.
- Appendix D's machine-learning-efficacy metrics and whether their averaging hides poorly synthesized high-value columns.
- A stronger privacy audit using membership and attribute inference attacks.

## Related Papers

- **PrivLava:** The closest relational synthesis baseline; also uses latent variables for foreign-key correlations but relies on graphical/marginal models and supports differential privacy.
- **SDV:** Uses hierarchical Gaussian-copula synthesis and conditional key lookups; ClavaDDPM targets its scalability and dependency-modeling limitations.
- **TabDDPM:** Supplies the main diffusion inspiration and an important backbone baseline; ClavaDDPM replaces separate multinomial diffusion with a unified Gaussian representation and adds relational conditioning.
- **TabSyn:** Uses latent diffusion for single-table synthesis and is discussed as a possible richer alternative to GMM latent learning.

## Open Questions

- Can the cluster bottleneck be learned end-to-end while retaining interpretable relational labels and scalable conditional sampling?
- How much long-range mutual information is lost by the diagonal-GMM approximation, and can that loss be estimated before synthesis?
- Can multi-parent generation model the joint condition directly rather than reconcile independent conditional samples through nearest-neighbor matching?
- How should the method handle cycles, temporal dependencies, composite keys, and integrity constraints beyond foreign keys?
- Can ClavaDDPM be trained with record- or entity-level differential privacy without destroying rare group structures and multi-hop correlations?
