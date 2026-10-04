# Stage-2 pages: provenance

| Repo file | Source (Quant workspace) | sha256 | How it's published |
|---|---|---|---|
| `data/processed/stage2/stage2_robustness.md` | Quant's stage-2 robustness appendix (`justina_shortlist/`, 2026-10-04 ET; renamed, bytes unchanged) | `289114d045ea97f3f6d92f0870f8472b320b81e6a55395274010176eec4b2b14` | Rendered by `scripts/build_stage2_pages.py` to `docs/methods/stage2_robustness.html`. The text is unchanged; only the lab header, footer and a provenance line are added. |
| `docs/methods/stage2_demiguel_kwz.html` | Quant's teaching note (`methods/stage2_demiguel_kwz.html`) | **pending.** Quant is revising the note; CoS will send its final sha256 | Byte-for-byte copy, never restyled. It's copied only when `TEACHING_SHA256` in `scripts/build_stage2_pages.py` matches. |

The appendix carries the KWZ correction (KWZ falls back to GMV, not EW; §1) and the DeMiguel placebo result (OOS p = 0.08, in-sample p = 0.01; §2.3). Nothing was re-run for these pages.
