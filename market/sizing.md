# Market Sizing: TAM / SAM / SOM and Funding Totals

Prepared 2026-09-26. Every derived number is labelled **ESTIMATE** and shows its method. Sourced inputs carry their source and grade (A peer-reviewed/primary, B press/analyst/tertiary, D marketing/analyst-marketing).

## 1. Funding: what we could verify

### 1a. Sector-level (venture, US + Europe, PitchBook-based)
| Period | Figure | Scope | Source |
|---|---|---|---|
| 2023 | **Neuro med-device venture: $1.3B across 43 deals** | Med device, "Neuro" indication | HSBC Innovation Banking, *2023 Annual Healthcare Venture Report*, p.48 (B; PDF text extracted) |
| 2023 | Neuro **biopharma**: $2.6B / 87 deals; first financings $675M / 20 deals | Drugs, not devices (context only) | Same report, p.14 and p.10 (B) |
| 2024 | "**neurotechnology companies received $1.2 billion in venture capital funding, more than any other type of medical device**" | Neurotech devices | Ruiz-Mateos Serrano et al., *Sci Adv* 2026, doi:10.1126/sciadv.aee8595 (A), citing the HSBC Venture Healthcare Report (ref. 38) |
| 1H 2025 → 1H 2026 | Neuro **biopharma**: $1.8B (1H25) → $2.5B (2H25) → $1.2B (1H26), 43 deals in 1H26 | Drugs (context) | HSBC *2026 Mid-Year Healthcare Venture Report*, p.14 (B) |
| 1H 2026 | "Neuro remained the strongest medtech investment category in 1H 2026 … continued investor conviction in both neurotechnology and BCI platforms". "BCI may also be the highest risk category, with Science ($1.5B post-money), Merge Labs ($850M) and Neuralink ($9B post-money in its 2025 deal)" | Med device | HSBC 1H26, p.49 (B) |
| 1H 2026 | First financings into neuro "dominated by BCI technologies, with Merge Labs ($252M …) and Nia Therapeutics ($27M)". Neurostim first financings: 4 deals, $60M combined | Med device | HSBC 1H26, p.45 (B) |

The HSBC 2024 and 2025 annual PDFs are image-based. Their text could not be extracted, so no per-year device figure was taken from them. The HSBC 1H26 chart on p.49 has neuro bars for '23–1H'26, but they could not be matched to labels reliably and were **not used**.

### 1b. Company rounds 2021–2026 (opened sources only)
| Company | Round | Amount | Date | Source (grade) |
|---|---|---|---|---|
| Precision Neuroscience | Series A | $12M | May 2021 | Wikipedia (B-) |
| Precision Neuroscience | Series B | $41M | Jan 2023 | Wikipedia (B-) |
| Paradromics | Venture | $33M | 2023 | Wikipedia (B-) |
| Synchron | Series C | $75M | Dec 2022 | Synchron newsroom (D) |
| Blackrock Neurotech | Strategic (Tether, majority stake) | $200M | Apr 2024 | Tether release via Wayback (D) |
| Precision Neuroscience | Series C | $102M | Dec 2024 | Wikipedia (B-) |
| Neuralink | Series E | $650M ($9B post) | Jun 2025 | Neuralink blog title (D) + HSBC (B) |
| Synchron | Series D | $200M | Nov 2025 | Synchron newsroom (D) |
| Merge Labs | Seed | $250M ($850M valuation) | Jan 2026 | TechCrunch (B) + HSBC (B) |
| Science Corp. | Series C | $230M ($1.5B post) | Mar 2026 | Science newsroom (D) + HSBC (B) |
| **Sum of verified rounds** | | **$1.793B** | 2021–2026 | Arithmetic over the rows above |

Reported but **not opened** (headline only): Neuralink $205M (Jul 2021, CNBC); Neuralink $280M Series D (Aug 2023, Reuters/CNN); Neuralink +$43M (Nov 2023, TechCrunch). Adding these gives **~$2.32B** across ten companies' disclosed rounds. This is a *floor* for invasive/next-gen BCI only. Non-invasive vendors' funding was not verified.

**Reading:** capital is highly concentrated. Seven companies account for about $1.8–2.3B. Sector-wide neurotech device VC runs at roughly **$1.2–1.3B per year** (2023, 2024).

## 2. Top-down (published analyst figures, grade D, shown to expose their unreliability)
| Publisher | BCI market | Software share |
|---|---|---|
| Precedence Research (page opened) | **$2.94B (2025)** → $13.86B (2035), 16.77% CAGR | Hardware 63.97% / **Software 36.03%** (the page also claims software "dominates", which contradicts its own split) |
| MarketsandMarkets (page opened) | **$262M (2024)** → $506M (2029), 14.1% CAGR | — |
| Mayo Clin Proc Digit Health 2026 (A, citing "market reports") | "$12 billion in implant revenue … by 2045" | — |

The two "current market" figures differ by about **11x**. **Conclusion: top-down BCI market numbers are not decision-grade.** Bottom-up below is the primary method.

Top-down ESTIMATE for reference only: $2.94B × 36.03% = **~$1.06B "BCI software" (Precedence)**. Using M&M with the same share, ~$94M. **TAM range: ~$0.1B–$1.1B**, uncertainty about 11x.

## 3. Bottom-up (primary method): all ESTIMATEs

### Segment inputs
| # | Segment (buyer) | Count method | Count (ESTIMATE) | Annual contract value (ESTIMATE) | Comparable price anchors |
|---|---|---|---|---|---|
| S1 | Clinical-stage / implant neurotech companies (regulated tooling, FDA documentation, latency verification, governance) | HSBC: 43 neuro device deals in 2023. Assume a funded company raises about every 2 years → ~80–100 active VC-backed neuro device companies in US+EU. Widen to 150 for non-PitchBook/non-US | **80–150** | **$50k–$150k** | Flywheel (quote only), Aptible Production $499/mo + usage, AWS usage |
| S2 | Non-invasive / consumer neurotech (neural-privacy compliance, SDK data backend) | No sourced count. The landscape names 11. Assume a long tail of 10–25x | **100–300** | **$10k–$50k** | EmotivPRO team $2,689/yr/seat-bundle; NeuroPype startup $948–$1,188/yr |
| S3 | Academic / clinical research labs doing electrophysiology (paid: institutional/core-facility plans) | SfN "over 30,000" (about page) to "nearly 35,000" (homepage) members. Assume ~10 members per lab → 3,000–3,500 labs. Assume 30–50% use EEG/MEG/ephys → **900–1,750 labs** (SfN members only). Cross-check: DANDI has 2,208 registered users (same order of magnitude) | **900–1,750** (≥; non-SfN labs excluded) | **$2k–$10k** (institutional); individual academics expect **free** (NeuroPype, W&B academic, brainlife, DANDI are all free) | EmotivPRO Standard $1,068/yr |
| S4 | CNS pharma / CROs running EEG endpoints (21 CFR Part 11 EEG data platform) | HSBC: 43 neuro biopharma deals in 1H26 alone. Assume 50–150 sponsors or CROs with EEG-endpoint programs | **50–150** | **$100k–$300k** | Flywheel serves "10 of the top 20 biopharma" (imaging) |

### SAM (reachable with the blueprint product + compliance wedge) = Σ count × ACV
- S1: 80×$50k = $4.0M → 150×$150k = $22.5M
- S2: 100×$10k = $1.0M → 300×$50k = $15.0M
- S3: 900×$2k = $1.8M → 1,750×$10k = $17.5M. Realistic paying share 10–20%, so **$0.2M–$3.5M**
- S4: 50×$100k = $5.0M → 150×$300k = $45.0M
- **SAM ESTIMATE: ~$10M–$86M ARR potential** (S3 at the realistic paying share)

### SOM (year 3 after launch): ESTIMATE, bottom-up by logos
| Segment | Logos | ACV | ARR |
|---|---|---|---|
| S1 | 15 | $75k | $1.125M |
| S2 | 30 | $20k | $0.60M |
| S3 | 60 paying institutions | $4k | $0.24M |
| S4 | 3 | $150k | $0.45M |
| **Total** | 108 | | **~$2.4M ARR** |

That is about 3–25% of SAM depending on where SAM lands. Every logo count is an assumption to be validated by discovery interviews (see validation.md).

### TAM (broad, all neural-data software incl. clinical EEG/neuromodulation/pharma)
- ESTIMATE: **$0.1B–$1.1B**, from the top-down range above.
- There is no reliable bottom-up for clinical EEG in hospitals: hospital EEG vendor software was out of scope and no source was opened.

## 4. Key sizing conclusions
1. **Pure "picks and shovels for BCI hardware makers" is a small market today.** S1 alone is ESTIMATE $4–22M. The best-funded makers build in-house (Synchron's Chiral foundation model, Neuralink's vertical stack).
2. **Money is in regulated buyers.** Clinical-stage device makers and CNS pharma (S1 + S4) make up about 70–80% of the SAM range.
3. **Academics are a channel, not revenue.** Free, NIH/NSF-funded substitutes dominate (DANDI, OpenNeuro, brainlife, MNE).
4. **Consumer neurotech is newly regulated** (CO 2024, CA 2024, MT 2025, CT 2026). This makes S2 compliance a *why-now* wedge.
