# Stage-2 pages: provenance

| Repo file | Source (Quant workspace) | sha256 | How it's published |
|---|---|---|---|
| `data/processed/stage2/stage2_robustness.md` | Quant's stage-2 robustness appendix (`justina_shortlist/`, 2026-10-04 ET, including the §7 update after the rulings; renamed, bytes unchanged) | `c1ca949521e3132f9bae592acfcb5fe53fa323fdd48b646d6bc6b14963fbde17` | Rendered by `scripts/build_stage2_pages.py` to `docs/methods/stage2_robustness.html`. The text is unchanged; only the lab header, footer and a provenance line are added. |
| `docs/methods/stage2_demiguel.html` | Quant's final teaching note (`methods/stage2_demiguel.html`; CoS confirmed the hash 2026-10-04 08:25 ET; no scripts, no CDN) | `8091157e656d740ceae02f2f53ec75ff049c02a8e8c56364d05ce379a9e1625d` | Byte-for-byte copy, never restyled (excluded from `restyle_methods_shell`). It's copied only when the source matches `TEACHING_SHA256` in `scripts/build_stage2_pages.py`. The earlier `stage2_demiguel_kwz.html` (now a redirect note) is not published. |
| `data/processed/stage2/demiguel_book_rule.json` | Figures transcribed from Quant's Addendum 2 to the stage-2 prereg, §7 CIO Book rule | Addendum 2 body `f004527e2c41183ef679b7ca5b9de18bc9884ef1c64816201df9963c96496e0c` | Read by the hub (forward-tracked research line: DeMiguel S_k5 fails the Book rule) |

The appendix carries the KWZ correction (KWZ falls back to GMV, not EW; §1) and the DeMiguel placebo result (OOS p = 0.08, in-sample p = 0.01; §2.3). Nothing was re-run for these pages.
