"""The evidence pack: the ONLY things agents are allowed to cite.

Facts (F-ids) come from XBRL company facts, and derived ratios are computed here in
plain Python rather than by the model. Excerpts (S-ids) are verbatim passages from
the filing; web excerpts (W-ids) are the exact text a web page was cited for.
Anything an agent says has to trace back to one of these ids.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date


@dataclass
class Fact:
    id: str
    label: str
    value: float
    unit: str  # "USD", "shares", "pct", "x"
    period: str  # fiscal-year end date, e.g. 2025-09-27
    source: str  # "us-gaap:Revenues @ 0000320193-25-000079" or "derived: F1/F2"

    def display(self) -> str:
        return fmt(self.value, self.unit)


@dataclass
class Excerpt:
    id: str
    section: str  # "Business", "Risk Factors", "MD&A", or "Web"
    text: str
    url: str = ""
    title: str = ""


@dataclass
class EvidencePack:
    company: str
    ticker: str
    filing_url: str
    facts: list[Fact] = field(default_factory=list)
    excerpts: list[Excerpt] = field(default_factory=list)

    def next_id(self, prefix: str) -> str:
        items = self.facts if prefix == "F" else [e for e in self.excerpts if e.id.startswith(prefix)]
        return f"{prefix}{len(items) + 1}"

    def add_valuation(self, market_cap: float, as_of: str, source: str) -> list[Fact]:
        """Market cap (from cited web research) + multiples computed in code."""
        latest = {}
        for f in self.facts:
            if f.label not in latest or f.period >= latest[f.label].period:
                latest[f.label] = f
        new: list[Fact] = []

        def add(label, value, unit, src):
            f = Fact(self.next_id("F"), label, float(value), unit, as_of, src)
            self.facts.append(f)
            new.append(f)
            return f

        mc = add("Market cap", market_cap, "USD", source)
        ni, fcf, rev, nd = (latest.get(k) for k in ("Net income", "Free cash flow", "Revenue",
                                                     "Net debt (LT debt - cash)"))
        if ni and ni.value > 0:
            add("P/E (market cap / net income)", mc.value / ni.value, "x", f"derived: {mc.id} / {ni.id}")
        if fcf and fcf.value > 0:
            add("P/FCF", mc.value / fcf.value, "x", f"derived: {mc.id} / {fcf.id}")
            add("FCF yield", fcf.value / mc.value * 100, "pct", f"derived: {fcf.id} / {mc.id}")
        if rev and rev.value > 0:
            ev = mc.value + (nd.value if nd else 0.0)
            add("EV / revenue", ev / rev.value, "x",
                f"derived: ({mc.id} + {nd.id}) / {rev.id}" if nd else f"derived: {mc.id} / {rev.id} (no debt data)")
        return new

    def ids(self) -> set[str]:
        return {f.id for f in self.facts} | {e.id for e in self.excerpts}

    def get(self, id_: str) -> Fact | Excerpt | None:
        for x in (*self.facts, *self.excerpts):
            if x.id == id_:
                return x
        return None

    def to_prompt(self, sections: tuple[str, ...] | None = None) -> str:
        lines = [f"COMPANY: {self.company} ({self.ticker})", "", "FACTS (from XBRL; derived ratios computed in code):"]
        for f in self.facts:
            lines.append(f"[{f.id}] {f.label} | FY ending {f.period} | {f.display()}")
        lines += ["", "FILING EXCERPTS (verbatim from the 10-K):"]
        for e in self.excerpts:
            if e.section != "Web" and (sections is None or e.section in sections):
                lines.append(f"[{e.id}] ({e.section}) {e.text}")
        web = [e for e in self.excerpts if e.section == "Web"]
        if web and sections is None:
            lines += ["", "WEB EVIDENCE (text cited from public web pages by the research agent):"]
            lines += [f"[{e.id}] ({e.title or e.url}) {e.text}" for e in web]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return asdict(self)


def fmt(value: float, unit: str) -> str:
    if unit == "pct":
        return f"{value:.1f}%"
    if unit == "x":
        return f"{value:.2f}x"
    if unit == "shares":
        return f"{value / 1e9:.2f}B shares" if abs(value) >= 1e9 else f"{value / 1e6:.1f}M shares"
    a = abs(value)
    sign = "-" if value < 0 else ""
    if a >= 1e9:
        return f"{sign}${a / 1e9:.1f}B"
    if a >= 1e6:
        return f"{sign}${a / 1e6:.1f}M"
    return f"{sign}${a:,.0f}"


# ----------------------------------------------------------------------------- XBRL

# (key, label, candidate us-gaap tags in priority order, unit, kind)
METRICS: list[tuple[str, str, tuple[str, ...], str, str]] = [
    ("revenue", "Revenue", ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"), "USD", "flow"),
    ("gross_profit", "Gross profit", ("GrossProfit",), "USD", "flow"),
    ("operating_income", "Operating income", ("OperatingIncomeLoss",), "USD", "flow"),
    ("net_income", "Net income", ("NetIncomeLoss",), "USD", "flow"),
    ("rnd", "R&D expense", ("ResearchAndDevelopmentExpense",), "USD", "flow"),
    ("cfo", "Operating cash flow", ("NetCashProvidedByUsedInOperatingActivities",), "USD", "flow"),
    ("capex", "Capital expenditures", ("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"), "USD", "flow"),
    ("cash", "Cash & equivalents", ("CashAndCashEquivalentsAtCarryingValue",), "USD", "instant"),
    ("debt", "Long-term debt", ("LongTermDebt", "LongTermDebtNoncurrent", "LongTermNotesPayable", "ConvertibleNotesPayable", "SeniorNotes"), "USD", "instant"),
    ("equity", "Stockholders' equity", ("StockholdersEquity",), "USD", "instant"),
    ("diluted_shares", "Diluted shares", ("WeightedAverageNumberOfDilutedSharesOutstanding",), "shares", "flow"),
]


def _annual_series(facts: dict, tags: tuple[str, ...], unit: str, kind: str, years: int) -> tuple[str, list[dict]]:
    """Return (tag, rows) for the first tag with 10-K fiscal-year values, newest last.

    Keeps only full-year durations for flow items (a 10-K also restates quarters),
    and de-duplicates restatements by keeping the latest-filed value per period end.
    """
    gaap = facts.get("facts", {}).get("us-gaap", {})
    best: tuple[str, list[dict]] = ("", [])
    for tag in tags:
        rows = gaap.get(tag, {}).get("units", {}).get(unit, [])
        by_end: dict[str, dict] = {}
        for r in rows:
            if not str(r.get("form", "")).startswith("10-K"):
                continue
            if kind == "flow":
                if "start" not in r:
                    continue
                days = (date.fromisoformat(r["end"]) - date.fromisoformat(r["start"])).days
                if not 350 <= days <= 380:
                    continue
            prev = by_end.get(r["end"])
            if prev is None or r.get("filed", "") > prev.get("filed", ""):
                by_end[r["end"]] = r
        series = [by_end[k] for k in sorted(by_end)][-years:]
        # Prefer the tag whose data is most recent (companies switch tags over time).
        if series and (not best[1] or series[-1]["end"] > best[1][-1]["end"]):
            best = (tag, series)
    return best


def build_facts(companyfacts: dict, years: int = 4) -> list[Fact]:
    facts: list[Fact] = []
    latest: dict[str, Fact] = {}
    history: dict[str, list[Fact]] = {}

    def add(label: str, value: float, unit: str, period: str, source: str) -> Fact:
        f = Fact(f"F{len(facts) + 1}", label, float(value), unit, period, source)
        facts.append(f)
        return f

    series = {key: _annual_series(companyfacts, tags, unit, kind, years) for key, _, tags, unit, kind in METRICS}
    newest = max((rows[-1]["end"] for _, rows in series.values() if rows), default="")
    for key, label, tags, unit, kind in METRICS:
        tag, rows = series[key]
        # A tag the company stopped reporting years ago is stale, not "latest"; skip it.
        if rows and newest and (date.fromisoformat(newest) - date.fromisoformat(rows[-1]["end"])).days > 400:
            continue
        for r in rows:
            f = add(label, r["val"], unit, r["end"], f"us-gaap:{tag} @ {r.get('accn', '?')}")
            history.setdefault(key, []).append(f)
        if rows:
            latest[key] = history[key][-1]

    def ratio(label: str, num: str, den: str, unit: str = "pct", scale: float = 100.0) -> None:
        if num in latest and den in latest and latest[den].value:
            a, b = latest[num], latest[den]
            if a.period == b.period:
                add(label, a.value / b.value * scale, unit, a.period, f"derived: {a.id} / {b.id}")

    ratio("Gross margin", "gross_profit", "revenue")
    ratio("Operating margin", "operating_income", "revenue")
    ratio("Net margin", "net_income", "revenue")
    ratio("R&D as % of revenue", "rnd", "revenue")
    ratio("Return on equity", "net_income", "equity")

    rev = history.get("revenue", [])
    if len(rev) >= 2 and rev[-2].value:
        add("Revenue growth (YoY)", (rev[-1].value / rev[-2].value - 1) * 100, "pct", rev[-1].period,
            f"derived: {rev[-1].id} / {rev[-2].id} - 1")
    if len(rev) >= 4 and rev[-4].value > 0 and rev[-1].value > 0:
        cagr = ((rev[-1].value / rev[-4].value) ** (1 / 3) - 1) * 100
        add("Revenue CAGR (3-yr)", cagr, "pct", rev[-1].period, f"derived: ({rev[-1].id} / {rev[-4].id})^(1/3) - 1")

    if "cfo" in latest and "capex" in latest and latest["cfo"].period == latest["capex"].period:
        c, x = latest["cfo"], latest["capex"]
        fcf = add("Free cash flow", c.value - x.value, "USD", c.period, f"derived: {c.id} - {x.id}")
        if "revenue" in latest and latest["revenue"].period == fcf.period and latest["revenue"].value:
            add("FCF margin", fcf.value / latest["revenue"].value * 100, "pct", fcf.period,
                f"derived: {fcf.id} / {latest['revenue'].id}")
    if "debt" in latest and "cash" in latest and latest["debt"].period == latest["cash"].period:
        d, c = latest["debt"], latest["cash"]
        add("Net debt (LT debt - cash)", d.value - c.value, "USD", d.period, f"derived: {d.id} - {c.id}")
    sh = history.get("diluted_shares", [])
    if len(sh) >= 2 and sh[-2].value:
        add("Diluted share count change (YoY)", (sh[-1].value / sh[-2].value - 1) * 100, "pct", sh[-1].period,
            f"derived: {sh[-1].id} / {sh[-2].id} - 1")
    return facts
