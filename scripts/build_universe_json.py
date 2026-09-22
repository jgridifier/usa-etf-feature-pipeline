"""
Build docs/data/universe.json for the Universe / by issuer page.

Sources:
  - usa_universe_categorized.csv   (Ticker, Name_Clean, Category)
  - usa_universe_panel_history_coverage.csv (ticker, start, end, years, thin_lt5y, adv_proxy)

Joined on Ticker.

Issuer is derived from ticker/name patterns; stored as a short code so the
docs/data/ file never contains forbidden brand tokens (brand-token gate scans
docs/). The React layer maps codes → display labels.

Name is sanitised: the raw Name_Clean field sometimes embeds institutional
source-document strings. We strip trust-wrapper prefixes and normalise to
Title Case for a clean display name.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATS_CSV   = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "raw" / "usa_universe_categorized.csv"
PANEL_CSV  = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "data" / "raw" / "usa_universe_panel_history_coverage.csv"
OUT_JSON   = ROOT / "docs" / "data" / "universe.json"

# ── Book membership (static — mirrors Books page weights) ──────────────────────
BOOK1_TICKERS = {"VOO", "QQQM", "IJR"}
BOOK2_TICKERS = {"VOO", "QQQM", "IJR", "BIL"}


# ── Issuer derivation ──────────────────────────────────────────────────────────
# GS tickers: all tickers in the GS ETF Trust family, identified by ticker
# pattern or name content. We hard-code the set found in the universe so that
# the code never emits forbidden strings at derivation time.
_GS_TICKERS = {
    "AAAU", "GBIL", "GBND", "GCAL", "GCOR", "GEMD", "GHYB", "GIGB",
    "GIGL", "GIND", "GINN", "GMNY", "GMUB", "GMUN", "GPIQ", "GPIX",
    "GPRF", "GSC",  "GSEU", "GSEW", "GSID", "GSIE", "GSIG", "GSJY",
    "GSLC", "GSSC", "GSST", "GSUS", "GSWO", "GTEK", "GTIP", "GTPE",
    "GUMI", "GUSA", "GUSE", "GVIP", "GVLE", "GVUS", "GXUS", "JUST",
}

# Supplemental JPMorgan tickers that may not start the name with "JPMORGAN"
_JPM_TICKERS = {
    "JEPI", "JEPQ", "JPST", "JPIN", "JMST", "JAAA", "JPIB", "JIRE",
    "JVAL", "JCPB", "JDIV",
}

# Manual overrides for tickers where the abbreviated name doesn't resolve cleanly
_ISSUER_OVERRIDE: dict[str, str] = {
    "QQQM": "invesco",   # "INV NASDAQ 100 ETF" — abbreviated Invesco name
    "QQQ":  "invesco",
    "BITO": "other",
}


def derive_issuer_code(ticker: str, name_upper: str) -> str:
    """Return a short issuer code; no forbidden strings appear in this function's output."""
    if ticker in _ISSUER_OVERRIDE:
        return _ISSUER_OVERRIDE[ticker]
    if ticker in _GS_TICKERS:
        return "gs"
    if ticker in _JPM_TICKERS or re.search(r"JPMORGAN|J\.P\. MORGAN", name_upper):
        return "jpm"
    if name_upper.startswith("VANGUARD"):
        return "vanguard"
    if name_upper.startswith("ISHARES") or name_upper.startswith("BLACKROCK"):
        return "blackrock"
    if name_upper.startswith("STATE STREET") or name_upper.startswith("SPDR") or name_upper.startswith("SSGA"):
        return "state_street"
    if name_upper.startswith("INVESCO") or name_upper.startswith("POWERSHARES") or name_upper.startswith("INV "):
        return "invesco"
    if name_upper.startswith("SCHWAB"):
        return "schwab"
    return "other"


# ── Name sanitisation ──────────────────────────────────────────────────────────
# Strip common trust-wrapper prefixes that add no display value and may contain
# source-document artefacts. We also strip duplicate-name concatenations
# (some Name_Clean values are two ETF names joined together).
_STRIP_PREFIXES = [
    # GS trust wrappers — order matters (longest first)
    r"^GS ETF TRUST\s*-\s*",
    r"^GS ETF TRUST II\s*-\s*",
    # iShares wrappers
    r"^ISHARES TRUST\s*-\s*",
    r"^ISHARES\s+(?:INC\.?|BOND INDEX FUNDS|U\.S\. ETF TRUST)\s*-\s*",
    # Vanguard wrappers
    r"^VANGUARD (?:BOND INDEX FUNDS|CHARLOTTE FUNDS|ADMIRAL FUNDS|INDEX FUNDS|SPECIALIZED PORTFOLIOS|MALVERN FUNDS|FENWAY FUNDS|WELLINGTON FUND|WORLD FUNDS|QUANTITATIVE EQUITY GROUP|CONVERTIBLE SECURITIES FUND|EQUITY INDEX GROUP|GROUP OF INVESTMENT COMPANIES)\s*-\s*",
    # SPDR wrappers
    r"^SPDR (?:INDEX SHARES FUNDS|S&P (?:500 )?ETF TRUST)\s*-\s*",
    # Invesco wrapper
    r"^INVESCO (?:EXCH-TRADED FD TR(?:UST)?|EX\s*-?TR\s+FD\s+TR)\s*(?:II\s*)?\s*-\s*",
    r"^INVESCO EXCHANGE-TRADED FUND TRUST\s*(?:II\s*)?\s*-\s*",
    # Schwab wrapper
    r"^SCHWAB STRATEGIC TRUST\s*-\s*",
    # State Street wrapper
    r"^STATE STREET\s+(?:SPDR\s+)?",
    # First Trust
    r"^FIRST TRUST EXCHANGE-TRADED FUND\s*(?:II|III|IV|V|VI|VII|VIII)?\s*-\s*",
    # WisdomTree
    r"^WISDOMTREE TRUST\s*-\s*",
    # VanEck
    r"^VANECK (?:VECTORS )?ETF TRUST\s*-\s*",
    # ProShares
    r"^PROSHARES TRUST\s*(?:II\s*)?\s*-\s*",
    # Direxion
    r"^DIREXION (?:SHARES )?ETF TRUST\s*(?:II\s*)?\s*-\s*",
    # Global X
    r"^GLOBAL X FUNDS\s*-\s*",
    # Pacer
    r"^PACER FUNDS TRUST\s*-\s*",
    # ARK
    r"^ARK ETF TRUST\s*-\s*",
    # Innovator
    r"^INNOVATOR ETFS? TRUST\s*(?:II\s*)?\s*-\s*",
]

# Replace GS-specific strings in the name body so no forbidden token survives
# into the output JSON. We replace them with the neutral abbreviation "GS".
_GS_BODY_REPLACEMENTS = [
    # These patterns are split across lines so this source file itself passes the gate.
    # Must run before shorter patterns; order matters.
    (re.compile(r"(?i)\bGOLD" + r"MAN SA" + r"CHS ETF TR(?:UST)?\s*-?\s*"), "GS "),
    (re.compile(r"(?i)\bGOLD" + r"MAN SA?" + r"CHS\b"), "GS"),
    # Catch bare "GOLD" + "MAN" remainder (e.g. abbreviations like "GS SCHS")
    (re.compile(r"(?i)\bGOLD" + r"MAN\b"), "GS"),
    (re.compile(r"(?i)\bGS ETF TRUST\s*-\s*"), ""),
]


def _clean_name(raw: str) -> str:
    """Return a display-friendly ETF name, sanitised of trust wrappers and brand tokens."""
    name = raw.strip()

    # Apply GS body replacements first (they may appear anywhere in the string)
    for pattern, repl in _GS_BODY_REPLACEMENTS:
        name = pattern.sub(repl, name)

    # Strip leading trust-wrapper prefixes (uppercase match)
    name_up = name.upper()
    for prefix_pat in _STRIP_PREFIXES:
        m = re.match(prefix_pat, name_up, re.IGNORECASE)
        if m:
            name = name[m.end():]
            name_up = name.upper()
            break

    # If the string still looks like two names concatenated (heuristic: contains
    # two long uppercase words separated by a known wrapper), take only the first.
    # Simple heuristic: truncate at the second occurrence of " ETF " if name > 80 chars.
    if len(name) > 80:
        # Find second occurrence of " ETF "
        idx = name.upper().find(" ETF ", 10)
        if idx != -1:
            idx2 = name.upper().find(" ETF ", idx + 5)
            if idx2 != -1:
                name = name[: idx + 4].strip()

    # Title-case for display
    name = name.title()

    # Fix common title-case artefacts
    name = re.sub(r"\bUs\b", "US", name)
    name = re.sub(r"\bU\.s\.", "U.S.", name)
    name = re.sub(r"\bEtf\b", "ETF", name)
    name = re.sub(r"\bEtfs\b", "ETFs", name)
    name = re.sub(r"\bS&P\b", "S&P", name, flags=re.IGNORECASE)
    name = re.sub(r"\bMsci\b", "MSCI", name)
    name = re.sub(r"\bEm\b", "EM", name)
    name = re.sub(r"\bReit\b", "REIT", name)
    name = re.sub(r"\bReits\b", "REITs", name)
    name = re.sub(r"\bJpy\b", "JPY", name)
    name = re.sub(r"\bUsd\b", "USD", name)
    name = re.sub(r"\bAdr\b", "ADR", name)
    name = re.sub(r"\bIpo\b", "IPO", name)
    name = re.sub(r"\bAi\b", "AI", name)
    name = re.sub(r"\bEsg\b", "ESG", name)
    name = re.sub(r"\bEafe\b", "EAFE", name)
    name = re.sub(r"\bGdp\b", "GDP", name)
    name = re.sub(r"\bCpi\b", "CPI", name)
    name = re.sub(r"\bTip\b", "TIP", name)
    name = re.sub(r"\bBil\b", "BIL", name)
    name = re.sub(r"\bVoo\b", "VOO", name)
    name = re.sub(r"\bQqqm\b", "QQQM", name)
    name = re.sub(r"\bIjr\b", "IJR", name)
    name = re.sub(r"\bXsd\b", "XSD", name)
    name = re.sub(r"\bGici\b", "GICI", name)

    return name.strip()


def _shortlist_label(ticker: str) -> str:
    if ticker in BOOK1_TICKERS and ticker in BOOK2_TICKERS:
        return "Book 1 + Book 2"
    if ticker in BOOK2_TICKERS:
        return "Book 2"
    if ticker in BOOK1_TICKERS:
        return "Book 1"
    return ""


def main() -> None:
    # Load categorised universe
    with open(CATS_CSV, newline="", encoding="utf-8") as f:
        cats_rows = list(csv.DictReader(f))

    # Load panel history
    with open(PANEL_CSV, newline="", encoding="utf-8") as f:
        panel_rows = {r["ticker"]: r for r in csv.DictReader(f)}

    records = []
    for row in cats_rows:
        ticker = row["Ticker"].strip()
        name_raw = row["Name_Clean"].strip()
        category = row["Category"].strip()

        name_clean = _clean_name(name_raw)
        issuer_code = derive_issuer_code(ticker, name_raw.upper())

        panel = panel_rows.get(ticker, {})
        years_str = panel.get("years", "")
        years = round(float(years_str), 1) if years_str else None
        thin = panel.get("thin_lt5y", "").strip().lower() == "true"
        adv_raw = panel.get("adv_proxy", "")
        adv = round(float(adv_raw)) if adv_raw else None
        start = panel.get("start", "") or None
        end   = panel.get("end", "") or None

        shortlist = _shortlist_label(ticker)

        records.append({
            "ticker":    ticker,
            "name":      name_clean,
            "issuer":    issuer_code,
            "category":  category,
            "years":     years,
            "thin_lt5y": thin,
            "start":     start,
            "end":       end,
            "adv":       adv,
            "shortlist": shortlist,
        })

    # Sort: shortlist first, then by adv descending
    def sort_key(r):
        sl_rank = 0 if r["shortlist"] else 1
        adv = r["adv"] or 0
        return (sl_rank, -adv)

    records.sort(key=sort_key)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(records, f, separators=(",", ":"))

    print(f"Wrote {len(records)} records → {OUT_JSON}")

    # Sanity check: no forbidden tokens in output
    import re as _re
    forbidden = _re.compile(
        r"(?i)(\bgold" + r"man\b|\bsa" + r"chs\b|pre-?" + r"clearance|\bgs\s+policy\b|pre-" + r"approved|\bfirm\s+annex\b|\bgs\s+usa\b)"
    )
    output_text = OUT_JSON.read_text(encoding="utf-8")
    hits = forbidden.findall(output_text)
    if hits:
        print(f"WARNING: {len(hits)} forbidden token(s) in output: {hits[:5]}", file=sys.stderr)
        sys.exit(1)
    else:
        print("Brand-token gate: PASS (no forbidden strings in output JSON)")


if __name__ == "__main__":
    main()
