"""Shared gate helper: cash-like tagging and excess-of-BIL Sharpe.

Part A of the NLS GMV v2 ticket (cash-null audit follow-up). Pure functions, no I/O
side effects beyond reading the committed CSVs they are pointed at.

* ``cash_like`` / ``short_duration`` tags live as boolean columns in
  ``data/raw/usa_universe_categorized.csv``. ``cash_like`` names (T-bill / floating-rate /
  ultrashort, duration <= ~1y) can be removed from the eligible set with
  :func:`filter_cash_like`. Runners call it ONCE on the shared eligible list, so the
  exclusion applies to the method and every null by construction. The flag defaults to
  ``True`` for new gates; archived trial dataclasses pin ``exclude_cash_like=False`` so
  their committed outputs are unchanged.
* ``near_cash`` is a stored boolean column like the other two tags (tagged by hand and reviewed; never
  derived at runtime). It never removes a name from any gate.
* Composition tripwire (default-on for every gate): average OOS share in cash_like + short_duration +
  near_cash names, method and primary null, VOID if either is > 50%. Sleeves are looked through to
  constituents; "not computable" is reported, never read as 0%, and blocks a PASS
  (``INCOMPLETE_LABEL``) unless the ticket opts out with a written reason.
* Risk-free rate: BIL's priced monthly total return from the committed monthly panel from
  BIL's first full month on; before that, FRED ``TB3MS`` / 1200 (``data/raw/fred_tb3ms.csv``).
  :func:`window_rf_coverage` reports the share of a window that uses the fallback.
* ``Sharpe_exBIL = mean(r - rf) * 12 / (std(r - rf, ddof=1) * sqrt(12))`` (arithmetic,
  monthly). ``Sharpe_rf0`` stays the repo's legacy CAGR / vol (``vol_target.sharpe_rf0``)
  and is labelled "legacy (rf = 0)" wherever it is shown.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from .vol_target import annualized_vol, max_drawdown, sharpe_rf0

MONTHS_PER_YEAR = 12
CASH_LIKE = frozenset({"BIL", "SGOV", "SHV", "GBIL", "USFR", "GSST", "GUMI"})
SHORT_DURATION = frozenset({"SHY", "SPTS", "BSV", "STIP"})
# Expected stored tags (documentation / tests). The universe file's boolean columns are the source of
# truth; nothing derives a tag from fund names at runtime. New loan funds are tagged by hand and reviewed.
NEAR_CASH = frozenset({"FTSL", "SRLN"})
EQUITY_ONLY_COLUMN = "equity_only"
EQUITY_ONLY = frozenset("""
ACWI ACWX ASHS BBC BINV BLDG BUSA DFSI DFUS DGRO DVY DXJ EEM EFA EFAV EFV ESGD ESGU EWC EWJ EZU FEZ
GSID GSIE GSLC GSSC GSUS GSWO GUSA HEFA IEFA IEUR IEV IJH IJJ IJK IJR IJS IJT INDA IQLT IUSV IVE IVV
IWB IWC IWD IWM IWN IWO IWP IWR IWS IWV IYY JPXN JUST KBE KRE LOUP MDY PID PRF QQQ QQQM QUAL SCHA
SCHF SCHM SCHX SCZ SDIV SDY SPY SPYM SPYV SUSA TMDV USMV VEA VEU VGK VIOG VLUE VO VOO VOOV VTI VTV
VTWO VV VXF VYM XBI XRT XSD
""".split())
CASH_LIKE_COLUMN = "cash_like"
SHORT_DURATION_COLUMN = "short_duration"
NEAR_CASH_COLUMN = "near_cash"
RF_TICKER = "BIL"
SHARPE_RF0_LABEL = "legacy (rf = 0)"
SHARPE_EXBIL_LABEL = "excess of BIL"

_REPO = Path(__file__).resolve().parents[2]
DEFAULT_PANEL = _REPO / "data" / "raw" / "usa_universe_panel_monthly_returns.csv"
DEFAULT_TB3MS = _REPO / "data" / "raw" / "fred_tb3ms.csv"


# --------------------------------------------------------------------------- tags
def _bool_col(universe: pd.DataFrame, col: str) -> pd.Series:
    if col not in universe.columns:
        raise KeyError(f"universe is missing the '{col}' tag column")
    s = universe[col]
    if s.dtype != bool:
        s = s.astype(str).str.strip().str.lower().map({"true": True, "false": False, "1": True, "0": False})
        if s.isna().any():
            raise ValueError(f"non-boolean values in '{col}'")
    return s.astype(bool)


def tagged_tickers(universe: pd.DataFrame, col: str) -> frozenset[str]:
    tick = universe["Ticker"].astype(str).str.strip().str.upper()
    return frozenset(tick[_bool_col(universe, col).to_numpy()])


def equity_only_tickers(universe: pd.DataFrame) -> frozenset[str]:
    return tagged_tickers(universe, EQUITY_ONLY_COLUMN)


def cash_like_tickers(universe: pd.DataFrame) -> frozenset[str]:
    return tagged_tickers(universe, CASH_LIKE_COLUMN)


def short_duration_tickers(universe: pd.DataFrame) -> frozenset[str]:
    return tagged_tickers(universe, SHORT_DURATION_COLUMN)


def near_cash_tickers(universe: pd.DataFrame) -> frozenset[str]:
    return tagged_tickers(universe, NEAR_CASH_COLUMN)


def is_cash_like(ticker: str, universe: pd.DataFrame) -> bool:
    return str(ticker).strip().upper() in cash_like_tickers(universe)


def filter_cash_like(names: Iterable[str], universe: pd.DataFrame,
                     exclude_cash_like: bool = True) -> list[str]:
    """Return ``names`` (order kept) without cash-like tickers when the flag is on.

    Call this once on the eligible list that feeds the method AND every null.
    """
    names = list(names)
    if not exclude_cash_like:
        return names
    cash = cash_like_tickers(universe)
    return [t for t in names if str(t).upper() not in cash]


def apply_gate_universe(panel: pd.DataFrame, universe: pd.DataFrame,
                        exclude_cash_like: bool = True) -> pd.DataFrame:
    """Drop cash-like columns from a returns panel shared by all strategies of a gate."""
    return panel.loc[:, filter_cash_like(panel.columns, universe, exclude_cash_like)]


def run_gate_strategies(panel: pd.DataFrame, universe: pd.DataFrame,
                        strategies: Mapping[str, "callable"],
                        exclude_cash_like: bool = True) -> dict[str, pd.Series]:
    """Evaluate every strategy (method and nulls) on the SAME filtered eligible panel.

    Each strategy is ``f(panel) -> weights Series`` indexed by ticker. Raises if any
    strategy returns weight on a name outside the eligible set.
    """
    eligible = apply_gate_universe(panel, universe, exclude_cash_like)
    allowed = set(eligible.columns)
    out = {}
    for name, fn in strategies.items():
        w = pd.Series(fn(eligible), dtype=float)
        bad = sorted(set(w.index[w.abs() > 0]) - allowed)
        if bad:
            raise ValueError(f"strategy {name!r} holds names outside the gate universe: {bad}")
        out[name] = w
    return out


# ------------------------------------------------ composition tripwire (default-on, every gate)
COMPOSITION_TAG_COLUMNS = (CASH_LIKE_COLUMN, SHORT_DURATION_COLUMN, NEAR_CASH_COLUMN)
COMPOSITION_MAX_SHARE = 0.50
INCOMPLETE_LABEL = "INCOMPLETE: composition not computable"


def look_through(weights: pd.DataFrame, constituents: pd.DataFrame | None = None) -> pd.DataFrame:
    """Expand sleeve holdings to constituent tickers.

    ``weights``: long format with ``date``, ``ticker`` (a ticker or a sleeve key) and ``weight``.
    ``constituents``: ``sleeve``, ``ticker``, ``weight`` (within-sleeve weights, summing to 1 per sleeve)
    and optionally ``date`` for time-varying membership. Rows whose holding is not a sleeve key pass
    through unchanged.
    """
    if constituents is None or constituents.empty:
        return weights.copy()
    c = constituents.rename(columns={"ticker": "_constituent", "weight": "_within"})
    keys = ["sleeve", "date"] if "date" in c.columns else ["sleeve"]
    sums = c.groupby(keys)["_within"].sum()
    if not np.allclose(sums.to_numpy(), 1.0, atol=1e-8):
        raise ValueError("within-sleeve constituent weights must sum to 1 per sleeve")
    is_sleeve = weights["ticker"].isin(set(c["sleeve"]))
    held = weights.loc[is_sleeve].rename(columns={"ticker": "sleeve"})
    expanded = held.merge(c, on=keys, how="left")
    if expanded["_constituent"].isna().any():
        raise ValueError("sleeve constituents missing for some sleeve/date")
    expanded["ticker"] = expanded.pop("_constituent")
    expanded["weight"] = expanded["weight"] * expanded.pop("_within")
    expanded = expanded.drop(columns="sleeve")
    return pd.concat([weights.loc[~is_sleeve], expanded[weights.columns]], ignore_index=True)


def composition_shares(weights: pd.DataFrame, universe: pd.DataFrame, *,
                       constituents: pd.DataFrame | None = None,
                       group_cols: Sequence[str] = ("strategy_id",)) -> pd.DataFrame:
    """Average share over the OOS window (mean over rebalance dates) in tagged names, per strategy.

    Reports ``cash_like``, ``short_duration`` and ``near_cash`` shares and the combined
    ``cash_duration_share_mean`` (the tripwire metric). Sleeves are looked through to constituents; a
    group holding anything that is neither a universe ticker nor a sleeve with constituents is
    ``computable = False`` with NaN shares (never read as 0%).
    """
    known = set(universe["Ticker"].astype(str).str.strip().str.upper())
    tags = {col: tagged_tickers(universe, col) for col in COMPOSITION_TAG_COLUMNS}
    rows = []
    for key, w in weights.groupby(list(group_cols)):
        key = key if isinstance(key, tuple) else (key,)
        row = dict(zip(group_cols, key))
        try:
            x = look_through(w, constituents)
            unknown = sorted({t for t in x["ticker"].astype(str) if t.strip().upper() not in known})
        except ValueError as exc:
            x, unknown = None, [str(exc)]
        if unknown:
            row.update({f"{c}_share_mean": np.nan for c in COMPOSITION_TAG_COLUMNS},
                       cash_duration_share_mean=np.nan, computable=False,
                       not_computable_reason="no constituent weights for: " + ", ".join(map(str, unknown)))
        else:
            n = x["date"].nunique()
            tick = x["ticker"].astype(str).str.upper()
            shares = {c: float(x.loc[tick.isin(t), "weight"].sum() / n) for c, t in tags.items()}
            row.update({f"{c}_share_mean": v for c, v in shares.items()},
                       cash_duration_share_mean=float(sum(shares.values())), computable=True,
                       not_computable_reason="")
        rows.append(row)
    return pd.DataFrame(rows)


def composition_tripwire(weights: pd.DataFrame, universe: pd.DataFrame, *, method: str, primary_null: str,
                         constituents: pd.DataFrame | None = None, opt_out: bool = False,
                         opt_out_reason: str | None = None, max_share: float = COMPOSITION_MAX_SHARE,
                         strategy_col: str = "strategy_id") -> dict:
    """Default-on composition tripwire for every gate.

    Metric: average share over the OOS window in cash_like + short_duration + near_cash names combined,
    for the method AND the primary null. VOID if either is strictly greater than ``max_share`` (50%).
    ``NOT COMPUTABLE`` if either cannot be looked through to tickers. A ticket may opt out only with a
    written reason (``opt_out=True, opt_out_reason="..."``), which the report prints; an opt-out without a
    reason raises. Effective N < 5 is a per-ticket tripwire and is not part of this default.
    """
    reason = (opt_out_reason or "").strip()
    if opt_out and not reason:
        raise ValueError("composition tripwire opt-out requires a written reason (opt_out_reason)")
    if reason and not opt_out:
        raise ValueError("opt_out_reason given without opt_out=True")
    sub = weights.loc[weights[strategy_col].isin([method, primary_null])]
    table = composition_shares(sub, universe, constituents=constituents, group_cols=(strategy_col,))
    table = table.set_index(strategy_col)
    missing = [s for s in (method, primary_null) if s not in table.index]
    if missing:
        raise ValueError(f"no weights for {missing}")
    m, p = table.loc[method], table.loc[primary_null]
    computable = bool(m.computable and p.computable)
    void_method = bool(computable and m.cash_duration_share_mean > max_share)
    void_null = bool(computable and p.cash_duration_share_mean > max_share)
    if opt_out:
        status = "OPTED OUT"
    elif not computable:
        status = "NOT COMPUTABLE"
    else:
        status = "VOID" if (void_method or void_null) else "PASS"
    return {"status": status, "max_share": max_share, "computable": computable,
            "method": method, "primary_null": primary_null,
            "method_share": float(m.cash_duration_share_mean), "null_share": float(p.cash_duration_share_mean),
            "void_method": void_method, "void_null": void_null,
            "opt_out": bool(opt_out), "opt_out_reason": reason or None,
            "not_computable_reason": "; ".join(r for r in (m.not_computable_reason, p.not_computable_reason) if r),
            "table": table.reset_index()}


def _pct(x: float) -> str:
    return "not computable" if x != x else f"{x:.2%}"


def composition_report_lines(result: dict) -> list[str]:
    """Markdown lines every gate report prints for the composition tripwire."""
    lines = ["## Composition tripwire (cash_like + short_duration + near_cash, default-on)", "",
             f"Status: **{result['status']}** (VOID if the method or the primary null averages > "
             f"{result['max_share']:.0%} over the OOS window).",
             f"- Method `{result['method']}`: {_pct(result['method_share'])}",
             f"- Primary null `{result['primary_null']}`: {_pct(result['null_share'])}"]
    if not result["computable"]:
        lines.append(f"- Composition not computable: {result['not_computable_reason']}. "
                     "This is not a pass; without a written opt-out a would-be PASS is "
                     f"\"{INCOMPLETE_LABEL}\".")
    if result["opt_out"]:
        lines.append(f"- Opted out by the ticket. Reason: {result['opt_out_reason']}")
    return lines + [""]


def final_gate_label(mechanical: str, composition: dict) -> str:
    """Combine a gate's own reading (PASS / FAIL / VOID) with the composition tripwire.

    VOID (the gate's own tripwires or the composition tripwire) wins; a FAIL stays FAIL; a would-be PASS
    becomes ``INCOMPLETE_LABEL`` when composition is not computable and not opted out with a reason.
    """
    mechanical = mechanical.upper()
    if mechanical not in {"PASS", "FAIL", "VOID"}:
        raise ValueError("mechanical reading must be PASS, FAIL or VOID")
    status = composition["status"]
    if mechanical == "VOID" or status == "VOID":
        return "VOID"
    if mechanical == "FAIL":
        return "FAIL"
    if status == "NOT COMPUTABLE":
        return INCOMPLETE_LABEL
    return "PASS"  # composition PASS, or OPTED OUT with a written reason (printed in the report)


# ------------------------------------------------------------------ risk-free rate
def load_tb3ms(path: str | Path = DEFAULT_TB3MS) -> pd.Series:
    """FRED TB3MS (percent, annualised, discount basis) -> monthly decimal rate TB3MS/1200."""
    df = pd.read_csv(path)
    date_col = "observation_date" if "observation_date" in df.columns else df.columns[0]
    s = pd.to_numeric(df["TB3MS"], errors="coerce")
    out = pd.Series(s.to_numpy() / 1200.0, index=pd.PeriodIndex(pd.to_datetime(df[date_col]), freq="M"),
                    name="tb3ms_monthly")
    if out.index.has_duplicates:
        raise ValueError("duplicate TB3MS months")
    return out.dropna().sort_index()


def load_bil_monthly(panel_path: str | Path = DEFAULT_PANEL) -> pd.Series:
    panel = pd.read_csv(panel_path, index_col=0, parse_dates=True)
    s = panel[RF_TICKER].astype(float)
    s.index = pd.PeriodIndex(s.index, freq="M")
    if s.index.has_duplicates:
        raise ValueError("duplicate months in the monthly panel")
    return s.sort_index()


def bil_first_full_month(bil: pd.Series) -> pd.Period:
    """First month with a priced BIL monthly return.

    Panel returns are month-end close to month-end close, so the inception month (no prior
    month-end price) is NaN and the first non-NaN month is BIL's first full month
    (2007-06 on the committed panel; BIL listed 2007-05-30).
    """
    first = bil.first_valid_index()
    if first is None:
        raise ValueError("BIL has no priced monthly return")
    if bil.loc[first:].isna().any():
        raise ValueError("BIL monthly return has gaps after its first full month")
    return first


def risk_free_monthly(bil: pd.Series | None = None, tb3ms: pd.Series | None = None) -> pd.DataFrame:
    """Monthly rf with its source: TB3MS/1200 before BIL's first full month, BIL after."""
    bil = load_bil_monthly() if bil is None else bil
    tb3ms = load_tb3ms() if tb3ms is None else tb3ms
    first = bil_first_full_month(bil)
    pre = tb3ms.loc[tb3ms.index < first]
    post = bil.loc[first:]
    rf = pd.concat([pd.DataFrame({"rf": pre, "source": "TB3MS"}),
                    pd.DataFrame({"rf": post, "source": "BIL"})])
    rf.index.name = "month"
    return rf.sort_index()


def _months(dates: Sequence) -> pd.PeriodIndex:
    idx = pd.Index(dates)
    if isinstance(idx, pd.PeriodIndex):
        return idx.asfreq("M")
    return pd.PeriodIndex(pd.to_datetime(idx), freq="M")


def align_rf(dates: Sequence, rf: pd.DataFrame) -> pd.DataFrame:
    months = _months(dates)
    missing = months.difference(rf.index)
    if len(missing):
        raise ValueError(f"no risk-free rate for months {list(missing.astype(str))[:5]}")
    return rf.loc[months]


def window_rf_coverage(dates: Sequence, rf: pd.DataFrame) -> dict:
    a = align_rf(dates, rf)
    n = len(a)
    fb = int((a["source"] == "TB3MS").sum())
    months = _months(dates)
    return {"start": str(months.min()), "end": str(months.max()), "n_months": n,
            "fallback_months": fb, "fallback_share": fb / n if n else float("nan"),
            "bil_share": (n - fb) / n if n else float("nan")}


# ------------------------------------------------------------------------- metrics
def sharpe_excess(returns: Sequence[float], rf: Sequence[float]) -> float:
    """Arithmetic annualised mean excess return / annualised std of excess returns."""
    ex = np.asarray(returns, float) - np.asarray(rf, float)
    if ex.size < 2 or not np.isfinite(ex).all():
        return float("nan")
    sd = ex.std(ddof=1)
    if sd <= 1e-15:
        # Holding exactly the risk-free asset: no excess return and no excess risk -> 0.
        return 0.0 if abs(ex.mean()) <= 1e-15 else float("nan")
    return float(ex.mean() * MONTHS_PER_YEAR / (sd * np.sqrt(MONTHS_PER_YEAR)))


def sharpe_exbil(returns: pd.Series, rf: pd.DataFrame | None = None) -> float:
    """Sharpe in excess of BIL (TB3MS fallback) for a date-indexed monthly return series."""
    r = pd.Series(returns, dtype=float).dropna()
    rf = risk_free_monthly() if rf is None else rf
    return sharpe_excess(r.to_numpy(), align_rf(r.index, rf)["rf"].to_numpy())


def gate_sharpe_table(series: Mapping[str, pd.Series] | pd.DataFrame,
                      rf: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per strategy: Sharpe_exBIL (headline), Sharpe_rf0 (legacy), vol, MaxDD, rf coverage.

    All series must share one date index (the gate window).
    """
    rf = risk_free_monthly() if rf is None else rf
    frame = pd.DataFrame(series) if not isinstance(series, pd.DataFrame) else series
    if frame.isna().any().any():
        raise ValueError("gate series must be complete on a common window")
    cov = window_rf_coverage(frame.index, rf)
    rfv = align_rf(frame.index, rf)["rf"].to_numpy()
    rows = []
    for name in frame.columns:
        r = frame[name].astype(float)
        rows.append({"strategy": name, "n_months": len(r), "start": cov["start"], "end": cov["end"],
                     "Sharpe_exBIL": sharpe_excess(r.to_numpy(), rfv),
                     "Sharpe_rf0_legacy": sharpe_rf0(r), "AnnVol": annualized_vol(r),
                     "MaxDD": max_drawdown(r), "rf_fallback_share": cov["fallback_share"],
                     "rf_bil_share": cov["bil_share"]})
    return pd.DataFrame(rows).set_index("strategy")
