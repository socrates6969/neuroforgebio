# Third-party data notice

The `greenspon2025_*` files in this folder are values digitised from, or derived from, a published figure:

> Greenspon C. M. et al., *Nature Biomedical Engineering* 9:935 (2025), Extended Data Fig. 1.
> doi:10.1038/s41551-024-01299-z, PMC12176618. Participants C1, P2, P3 (coded, as in the article).

- **Licence of the source article: CC BY-NC-ND 4.0.** These files are **not for redistribution**.
- **Use: internal testing only**, in this private repository. They reproduce the reviewed research
  numbers (research/somatosensory/code/REVIEW_cycle4.md) in the golden tests.
- They are **excluded from the wheel and sdist** (`pyproject.toml`, `MANIFEST.in`), and
  `tests/test_ce_release_guard.py` fails a build that contains any of them.
- Before any public or open-source release (decision D6), replace them. See
  `docs/features/channel-estimator.md`, "Before an open-source release".
- Legal basis and analysis: `legal/data-agreements/figure-data-memo.md` (nfb-legal, DRAFT pending advokat review).
