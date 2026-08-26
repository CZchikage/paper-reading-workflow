# v11 verified sources

Conference sources:
- NeurIPS: official proceedings.neurips.cc
- ICLR: official proceedings.iclr.cc
- ICML/AISTATS/UAI/COLT: official PMLR volumes
- SaTML: official accepted-papers pages

Journal hard filters use exact ISSNs via OpenAlex plus cited_by_count >= 10.

The PMLR parser is specialized for PMLR's `<div class="paper">` structure, because
the `abs` link text is not the paper title. This fixes the bug that caused all
PMLR conferences to disappear in v8-v10.
