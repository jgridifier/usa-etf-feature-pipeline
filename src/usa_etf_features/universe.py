"""Universe gate: approved CSV ∩ ¬ Appendix-3 / off-list deny."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd
import yaml

DEFAULT_APPENDIX3_DENY = frozenset(
    {"VUG", "IWF", "IVW", "IUSG", "DIA", "XLF", "XLU", "IYR", "UPRO", "AAXJ"}
)
DEFAULT_OFF_LIST = frozenset({"SMH", "SOXX", "SOXL", "PSI"})


class UniverseGateError(ValueError):
    """Raised when a ticker is not in the eligible set."""


def load_universe_config(path: str | Path | None = None) -> dict:
    if path is None:
        # default relative to repo root when installed editable / cwd
        candidates = [
            Path("config/universe.yaml"),
            Path(__file__).resolve().parents[2] / "config" / "universe.yaml",
        ]
        for c in candidates:
            if c.exists():
                path = c
                break
        else:
            return {
                "appendix3_deny": sorted(DEFAULT_APPENDIX3_DENY),
                "off_list_hard_deny": sorted(DEFAULT_OFF_LIST),
                "thin_history_tickers": ["QQQM", "LOUP", "GTEK", "GINN"],
                "ticker_column": "Ticker",
                "category_column": "Category",
                "source_section_column": "Source_Section",
            }
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_universe_csv(csv_path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if "Ticker" not in df.columns:
        raise ValueError(f"Universe CSV missing Ticker column: {csv_path}")
    df = df.copy()
    df["Ticker"] = df["Ticker"].astype(str).str.strip().str.upper()
    return df


def _deny_sets(config: dict | None) -> tuple[frozenset[str], frozenset[str]]:
    cfg = config or {}
    a3 = frozenset(t.upper() for t in cfg.get("appendix3_deny", DEFAULT_APPENDIX3_DENY))
    off = frozenset(t.upper() for t in cfg.get("off_list_hard_deny", DEFAULT_OFF_LIST))
    return a3, off


def approved_tickers(universe_df: pd.DataFrame) -> set[str]:
    return set(universe_df["Ticker"].astype(str).str.upper())


def eligible_tickers(
    universe_df: pd.DataFrame,
    config: dict | None = None,
) -> set[str]:
    """E = U_approved \\ APPENDIX3_DENY (and hard off-list)."""
    cfg = config or {}
    a3, off = _deny_sets(cfg)
    section_col = cfg.get("source_section_column", "Source_Section")
    u = approved_tickers(universe_df)
    tagged_a3: set[str] = set()
    if section_col in universe_df.columns:
        mask = (
            universe_df[section_col]
            .astype(str)
            .str.contains("APPENDIX\\s*3|Appendix\\s*3", case=False, regex=True, na=False)
        )
        tagged_a3 = set(universe_df.loc[mask, "Ticker"].astype(str).str.upper())
    deny = a3 | off | tagged_a3
    return u - deny


def assert_eligible(
    tickers: Iterable[str],
    universe_df: pd.DataFrame,
    config: dict | None = None,
) -> None:
    """Hard-fail any ticker not in eligible set (incl. SMH/SOXX/SOXL/PSI)."""
    eligible = eligible_tickers(universe_df, config)
    a3, off = _deny_sets(config)
    for raw in tickers:
        t = str(raw).strip().upper()
        if t not in eligible:
            reason = "off-list hard deny" if t in off else (
                "Appendix-3 deny" if t in a3 else "not in approved universe CSV"
            )
            raise UniverseGateError(
                f"Ticker {t} is not eligible ({reason}). "
                "Only USA pre-approved tickers minus Appendix 3 / off-list may be scored."
            )


def category_map(universe_df: pd.DataFrame, config: dict | None = None) -> dict[str, str]:
    cfg = config or {}
    cat_col = cfg.get("category_column", "Category")
    if cat_col not in universe_df.columns:
        return {t: "Unknown" for t in approved_tickers(universe_df)}
    out: dict[str, str] = {}
    for _, row in universe_df.iterrows():
        out[str(row["Ticker"]).upper()] = str(row[cat_col]) if pd.notna(row[cat_col]) else "Unknown"
    return out


def thin_history_set(config: dict | None = None) -> set[str]:
    cfg = config or load_universe_config()
    return {t.upper() for t in cfg.get("thin_history_tickers", ["QQQM", "LOUP", "GTEK", "GINN"])}
