"""Growth-mode portfolio construction + thematic rotation sleeve (Milestone 2).

Research tooling only — not investment advice.
M3 full optimizer study is out of scope; this module applies documented caps
and the Option-A core + proportional thematic funding rule.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .rotation import (
    assert_rotate_tickers_eligible,
    load_portfolio_constraints,
    signal_on_asof,
)
from .universe import UniverseGateError, assert_eligible, load_universe_config, load_universe_csv


def proportional_core_trim(
    core: dict[str, float],
    thematic_weights: dict[str, float],
) -> dict[str, float]:
    """
    Fund thematic sleeve by trimming core proportionally:
      w_i^core = CORE_i * (1 - sum w_thematic)
    Raises if thematic sum exceeds 1 or individual caps are violated by caller.
    """
    thematic_sum = float(sum(thematic_weights.values()))
    if thematic_sum < -1e-12:
        raise ValueError("thematic weights must be non-negative")
    if thematic_sum > 1.0 + 1e-9:
        raise ValueError(f"thematic sum {thematic_sum} exceeds 1.0")
    scale = 1.0 - thematic_sum
    out = {k: float(v) * scale for k, v in core.items()}
    for t, w in thematic_weights.items():
        out[t] = out.get(t, 0.0) + float(w)
    return out


def enforce_thematic_caps(
    thematic_weights: dict[str, float],
    thematic_cap: float = 0.25,
    single_cap: float = 0.15,
) -> dict[str, float]:
    """Clip single-name thematic weights and rescale sleeve to thematic_cap if needed."""
    w = {k: max(0.0, float(v)) for k, v in thematic_weights.items()}
    for k in list(w):
        if w[k] > single_cap + 1e-12:
            w[k] = single_cap
    s = sum(w.values())
    if s > thematic_cap + 1e-12 and s > 0:
        scale = thematic_cap / s
        w = {k: v * scale for k, v in w.items()}
    return w


def validate_weights(
    weights: dict[str, float],
    thematic_tickers: set[str],
    thematic_cap: float = 0.25,
    single_thematic_cap: float = 0.15,
    tol: float = 1e-8,
) -> None:
    s = sum(weights.values())
    if abs(s - 1.0) > tol:
        raise ValueError(f"weights must sum to 1 (±{tol}), got {s}")
    for t, w in weights.items():
        if w < -tol:
            raise ValueError(f"negative weight for {t}: {w}")
        if t.upper() in thematic_tickers and w > single_thematic_cap + tol:
            raise ValueError(f"thematic single-name cap {single_thematic_cap} breached by {t}={w}")
    them_sum = sum(w for t, w in weights.items() if t.upper() in thematic_tickers)
    if them_sum > thematic_cap + tol:
        raise ValueError(f"thematic sleeve cap {thematic_cap} breached: {them_sum}")


def build_rotated_portfolio(
    prices: pd.DataFrame,
    *,
    constraints: dict | None = None,
    asof: pd.Timestamp | None = None,
    use_vol_gate: bool = True,
    hysteresis_months: int | None = None,
    universe_df: pd.DataFrame | None = None,
    universe_config: dict | None = None,
    rotate_eligible: list[str] | None = None,
) -> pd.DataFrame:
    """
    Option-A core + rotate-in thematic sleeve (default eligible: XSD).

    When all thematic OFF → core_when_thematic_off.
    When ON → proportional core trim funding rotate_on_weight (capped).
    """
    cfg = constraints or load_portfolio_constraints()
    core = {k.upper(): float(v) for k, v in cfg.get("core_when_thematic_off", {}).items()}
    if abs(sum(core.values()) - 1.0) > 1e-8:
        raise ValueError("core_when_thematic_off must sum to 1")

    eligible = [t.upper() for t in (rotate_eligible or cfg.get("thematic_rotate_eligible", ["XSD"]))]
    assert_rotate_tickers_eligible(eligible, universe_df, universe_config)

    thematic_set = {t.upper() for t in cfg.get("thematic_tickers", eligible)}
    thematic_cap = float(cfg.get("thematic_cap", 0.25))
    single_cap = float(cfg.get("single_name_cap_thematic", 0.15))
    on_w = min(float(cfg.get("rotate_on_weight", 0.10)), single_cap)
    bench = str(cfg.get("rotate_benchmark", "VOO")).upper()
    hyst = cfg.get("hysteresis_months", 2) if hysteresis_months is None else hysteresis_months
    vol_q = float(cfg.get("vol_gate_quantile", 0.90))
    vol_mp = int(cfg.get("vol_gate_min_periods", 21))

    thematic_w: dict[str, float] = {}
    signal_rows: list[dict[str, Any]] = []
    for t in eligible:
        on = signal_on_asof(
            prices,
            t,
            asof=asof,
            benchmark=bench,
            use_vol_gate=use_vol_gate,
            hysteresis_months=int(hyst or 0),
            vol_quantile=vol_q,
            vol_min_periods=vol_mp,
        )
        thematic_w[t] = on_w if on else 0.0
        signal_rows.append({"ticker": t, "rotate_on": bool(on), "target_weight": thematic_w[t]})

    thematic_w = enforce_thematic_caps(thematic_w, thematic_cap=thematic_cap, single_cap=single_cap)
    # Zero out tiny remnants
    thematic_w = {k: v for k, v in thematic_w.items() if v > 1e-12}

    weights = proportional_core_trim(core, thematic_w)
    validate_weights(weights, thematic_set, thematic_cap=thematic_cap, single_thematic_cap=single_cap)

    rows = []
    on_map = {r["ticker"]: r["rotate_on"] for r in signal_rows}
    for t, w in weights.items():
        role = "thematic" if t in thematic_set else "core"
        rows.append(
            {
                "ticker": t,
                "weight": w,
                "role": role,
                "rotate_on": on_map.get(t, False) if role == "thematic" else False,
                "thesis_tag": "rotate_thematic" if role == "thematic" and w > 0 else (
                    "core_option_a" if role == "core" else "thematic_off"
                ),
                "mode": "growth_rotate",
            }
        )
    # Include eligible thematics at 0 for auditability when OFF
    present = {r["ticker"] for r in rows}
    for t in eligible:
        if t not in present:
            rows.append(
                {
                    "ticker": t,
                    "weight": 0.0,
                    "role": "thematic",
                    "rotate_on": on_map.get(t, False),
                    "thesis_tag": "thematic_off",
                    "mode": "growth_rotate",
                }
            )
    out = pd.DataFrame(rows).sort_values(["role", "weight"], ascending=[True, False]).reset_index(drop=True)
    return out


def build_static_from_scores(
    scores: pd.DataFrame,
    *,
    constraints: dict | None = None,
    n_holdings: int | None = None,
) -> pd.DataFrame:
    """
    Simple static growth sleeve from ranked scores (no rotate).
    Takes top-N by S_i with thematic/single caps; renormalizes to 1.
    """
    cfg = constraints or load_portfolio_constraints()
    thematic_set = {t.upper() for t in cfg.get("thematic_tickers", [])}
    thematic_cap = float(cfg.get("thematic_cap", 0.25))
    single_them = float(cfg.get("single_name_cap_thematic", 0.15))
    single_core = float(cfg.get("single_name_cap_core", 0.40))
    card_min = int(cfg.get("cardinality_min", 4))
    card_max = int(cfg.get("cardinality_max", 8))
    n = n_holdings or card_max
    n = max(card_min, min(n, card_max))

    df = scores.copy()
    if "ticker" not in df.columns:
        df = df.reset_index().rename(columns={"index": "ticker"})
    df["ticker"] = df["ticker"].astype(str).str.upper()
    if "S_i" not in df.columns:
        raise ValueError("scores must include S_i")
    df = df.sort_values("S_i", ascending=False)

    picked: list[str] = []
    them_w = 0.0
    for _, row in df.iterrows():
        if len(picked) >= n:
            break
        t = row["ticker"]
        is_them = t in thematic_set
        if is_them and them_w >= thematic_cap - 1e-12:
            continue
        picked.append(t)
        if is_them:
            # equal-weight later; reserve room
            them_w += single_them  # provisional

    if not picked:
        raise ValueError("no holdings selected from scores")

    # Equal weight then clip caps and renormalize
    w = {t: 1.0 / len(picked) for t in picked}
    for _ in range(8):
        for t in list(w):
            cap = single_them if t in thematic_set else single_core
            if w[t] > cap:
                w[t] = cap
        them_sum = sum(v for t, v in w.items() if t in thematic_set)
        if them_sum > thematic_cap:
            scale = thematic_cap / them_sum
            for t in list(w):
                if t in thematic_set:
                    w[t] *= scale
        s = sum(w.values())
        if s <= 0:
            raise ValueError("weights collapsed")
        w = {t: v / s for t, v in w.items()}
        # Check feasibility
        ok = all(
            (w[t] <= (single_them if t in thematic_set else single_core) + 1e-9) for t in w
        ) and sum(v for t, v in w.items() if t in thematic_set) <= thematic_cap + 1e-9
        if ok and abs(sum(w.values()) - 1.0) < 1e-8:
            break

    # Final hard clip for float residue then renorm
    for t in list(w):
        cap = single_them if t in thematic_set else single_core
        w[t] = min(w[t], cap)
    them_sum = sum(v for t, v in w.items() if t in thematic_set)
    if them_sum > thematic_cap:
        scale = thematic_cap / them_sum
        for t in list(w):
            if t in thematic_set:
                w[t] *= scale
    s = sum(w.values())
    w = {t: v / s for t, v in w.items()}
    validate_weights(w, thematic_set, thematic_cap=thematic_cap, single_thematic_cap=single_them)
    rows = [
        {
            "ticker": t,
            "weight": w[t],
            "role": "thematic" if t in thematic_set else "core",
            "rotate_on": False,
            "thesis_tag": "score_rank_static",
            "mode": "growth_static",
            "S_i": float(df.set_index("ticker").loc[t, "S_i"]) if t in set(df["ticker"]) else float("nan"),
        }
        for t in w
    ]
    return pd.DataFrame(rows).sort_values("weight", ascending=False).reset_index(drop=True)


def build_portfolio(
    scores: pd.DataFrame | None = None,
    prices: pd.DataFrame | None = None,
    *,
    rotate_thematic: bool = False,
    use_vol_gate: bool = False,
    hysteresis_months: int | None = None,
    constraints: dict | None = None,
    asof: pd.Timestamp | None = None,
    universe_csv: str | Path | None = None,
    universe_config: dict | None = None,
) -> pd.DataFrame:
    """Dispatch static vs rotate portfolio construction."""
    cfg = constraints or load_portfolio_constraints()
    uni_df = None
    uni_cfg = universe_config or load_universe_config()
    if universe_csv is not None:
        uni_df = load_universe_csv(universe_csv)

    if rotate_thematic:
        if prices is None:
            raise ValueError("--rotate-thematic requires prices panel")
        eligible = [t.upper() for t in cfg.get("thematic_rotate_eligible", ["XSD"])]
        if uni_df is not None:
            assert_eligible(eligible, uni_df, uni_cfg)
        else:
            assert_rotate_tickers_eligible(eligible)
        return build_rotated_portfolio(
            prices,
            constraints=cfg,
            asof=asof,
            use_vol_gate=use_vol_gate,
            hysteresis_months=hysteresis_months,
            universe_df=uni_df,
            universe_config=uni_cfg,
            rotate_eligible=eligible,
        )

    if scores is None:
        raise ValueError("scores required when rotate_thematic is False")
    return build_static_from_scores(scores, constraints=cfg)


# Back-compat stub name from M1
def build_portfolio_stub(scores: pd.DataFrame, *_args, **_kwargs) -> pd.DataFrame:
    return build_portfolio(scores=scores, rotate_thematic=False)
