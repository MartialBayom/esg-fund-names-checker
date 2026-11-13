"""Check a fund portfolio against the requirements its name triggers, and simulate name changes.

Issuer data (fossil revenues, controversies, ESG alignment) normally comes from a data vendor
(MSCI, Sustainalytics, ISS...). Here we generate a synthetic issuer universe with realistic sector
patterns so that the project is fully reproducible and free. Fund NAMES are real (GLEIF).
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from name_rules import CTB_KEYS, PAB_RULES, assess_name

THRESHOLD = 80.0                 # % of investments meeting E/S characteristics (ESMA)
MEANINGFUL_SI = 10.0             # assumption: "meaningful" sustainable investment share, configurable

SECTORS = {  # sector: (count, oil, gas, coal, power, weapons_p, tobacco_p, ungc_p, esg_p, si_p, plan_p)
    "Oil & Gas":     (30, (20, 90), (10, 60), (0, 2), (0, 5), 0.0, 0.0, 0.08, 0.15, 0.00, 0.30),
    "Utilities":     (35, (0, 3), (0, 40), (0, 25), (10, 90), 0.0, 0.0, 0.03, 0.55, 0.25, 0.60),
    "Mining":        (20, (0, 5), (0, 5), (0, 40), (0, 5), 0.0, 0.0, 0.10, 0.35, 0.05, 0.40),
    "Tobacco":       (6, (0, 0), (0, 0), (0, 0), (0, 0), 0.0, 1.0, 0.05, 0.10, 0.00, 0.20),
    "Aerospace & Defence": (15, (0, 0), (0, 0), (0, 0), (0, 0), 0.25, 0.0, 0.05, 0.40, 0.05, 0.40),
    "Industrials":   (60, (0, 2), (0, 3), (0, 1), (0, 2), 0.01, 0.0, 0.01, 0.85, 0.30, 0.60),
    "Technology":    (70, (0, 0), (0, 0), (0, 0), (0, 0), 0.0, 0.0, 0.01, 0.92, 0.40, 0.70),
    "Health Care":   (50, (0, 0), (0, 0), (0, 0), (0, 0), 0.0, 0.0, 0.01, 0.92, 0.45, 0.60),
    "Financials":    (60, (0, 0), (0, 0), (0, 0), (0, 0), 0.0, 0.0, 0.01, 0.88, 0.25, 0.60),
    "Consumer":      (55, (0, 0), (0, 0), (0, 0), (0, 0), 0.0, 0.02, 0.01, 0.85, 0.25, 0.50),
    "Renewables":    (25, (0, 0), (0, 5), (0, 0), (0, 0), 0.0, 0.0, 0.01, 0.98, 0.90, 0.90),
}


def issuer_universe(seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for sector, (n, oil, gas, coal, power, w, t, u, esg, si, plan) in SECTORS.items():
        for i in range(n):
            def rev(rng_range, p_zero=0.5):
                lo, hi = rng_range
                return 0.0 if hi == 0 or rng.random() < p_zero else round(float(rng.uniform(lo, hi)), 1)
            rows.append({
                "issuer": f"{sector.split()[0][:4].upper()}-{i + 1:03d}", "sector": sector,
                "oil_rev_pct": rev(oil, 0.1 if sector == "Oil & Gas" else 0.8),
                "gas_rev_pct": rev(gas, 0.3 if sector in ("Oil & Gas", "Utilities") else 0.9),
                "coal_rev_pct": rev(coal, 0.6),
                "high_ghg_power_rev_pct": rev(power, 0.4 if sector == "Utilities" else 0.95),
                "controversial_weapons": bool(rng.random() < w), "tobacco": bool(rng.random() < t),
                "ungc_violation": bool(rng.random() < u), "esg_aligned": bool(rng.random() < esg),
                "sustainable_investment": bool(rng.random() < si), "transition_plan": bool(rng.random() < plan),
                "impact_kpi": bool(rng.random() < si * 0.6),
            })
    df = pd.DataFrame(rows)
    df.loc[~df["esg_aligned"], ["sustainable_investment", "impact_kpi"]] = False
    return df


def random_portfolio(universe: pd.DataFrame, rng: np.random.Generator, n: int = 60, tilt: float = 0.0,
                     prefer: str | None = None) -> pd.DataFrame:
    """tilt > 0: the manager prefers ESG-aligned, low-fossil issuers (and the `prefer` flag, e.g. impact_kpi)."""
    clean = (universe["esg_aligned"] & (universe[["oil_rev_pct", "coal_rev_pct"]].sum(axis=1) == 0)
             & ~universe["ungc_violation"]).astype(float)   # most ESG managers already screen UNGC violators
    if prefer:
        clean = clean + universe[prefer].astype(float)
    p = np.exp(tilt * clean)
    p /= p.sum()
    idx = rng.choice(len(universe), size=n, replace=False, p=p)
    w = rng.dirichlet(np.ones(n)) * 100
    return universe.iloc[idx].assign(weight=w.round(3)).reset_index(drop=True)


def breaches(pf: pd.DataFrame, exclusions: str) -> pd.DataFrame:
    keys = CTB_KEYS if exclusions == "CTB" else list(PAB_RULES)
    out = []
    for k in keys:
        label, limit = PAB_RULES[k]
        hit = pf[k] if limit == "flag" else pf[k] >= limit
        for _, r in pf[hit].iterrows():
            out.append({"issuer": r["issuer"], "sector": r["sector"], "weight": r["weight"], "rule": label})
    return pd.DataFrame(out, columns=["issuer", "sector", "weight", "rule"])


@dataclass
class CheckResult:
    name: str
    categories: list[str]
    exclusions: str | None
    aligned_pct: float
    sustainable_pct: float
    transition_pct: float
    impact_pct: float
    breaches: pd.DataFrame = field(repr=False)
    issues: list[str] = field(default_factory=list)

    @property
    def compliant(self) -> bool:
        return not self.issues

    @property
    def weight_to_divest(self) -> float:
        return round(self.breaches.drop_duplicates("issuer")["weight"].sum(), 2) if len(self.breaches) else 0.0


def check(name: str, pf: pd.DataFrame) -> CheckResult:
    a = assess_name(name)
    aligned = pf.loc[pf["esg_aligned"], "weight"].sum()
    si = pf.loc[pf["sustainable_investment"], "weight"].sum()
    tr = pf.loc[pf["esg_aligned"] & pf["transition_plan"], "weight"].sum()
    imp = pf.loc[pf["impact_kpi"], "weight"].sum()
    br = breaches(pf, a.exclusions) if a.exclusions else breaches(pf.iloc[0:0], "CTB")
    issues = []
    if a.in_scope:
        if aligned < THRESHOLD:
            issues.append(f"only {aligned:.1f}% of investments meet the E/S characteristics (minimum 80%)")
        if len(br):
            issues.append(f"{br['issuer'].nunique()} issuers ({br.drop_duplicates('issuer')['weight'].sum():.1f}% "
                          f"of the fund) breach the {a.exclusions} exclusions")
        if "transition" in a.terms and tr < THRESHOLD:
            issues.append(f"only {tr:.1f}% of investments are aligned AND on a measurable transition path")
        if "impact" in a.terms and imp < THRESHOLD:
            issues.append(f"only {imp:.1f}% of investments have a measurable impact objective")
        if "sustainability" in a.terms and si < MEANINGFUL_SI:
            issues.append(f"only {si:.1f}% sustainable investments (assumed minimum {MEANINGFUL_SI:.0f}%)")
    return CheckResult(name, a.categories, a.exclusions, round(aligned, 1), round(si, 1), round(tr, 1),
                       round(imp, 1), br, issues)


def _remove_terms(name: str, terms: list[str], insert: str | None = None) -> str:
    out = name
    for i, t in enumerate(sorted(set(terms), key=len, reverse=True)):
        out = _replace_word(out, t, "\x00" if (insert and i == 0) else "")
    out = out.replace("\x00", insert or "")
    return " ".join(out.replace("- -", "-").split()).strip(" -")


def divest(pf: pd.DataFrame, exclusions: str) -> pd.DataFrame:
    """Sell the breaching issuers and scale the rest back to 100%."""
    bad = set(breaches(pf, exclusions)["issuer"])
    kept = pf[~pf["issuer"].isin(bad)].copy()
    kept["weight"] = kept["weight"] / kept["weight"].sum() * 100
    return kept


def options(name: str, pf: pd.DataFrame) -> pd.DataFrame:
    """Compare what the manager can do: sell, rename (several ways), or leave the scope."""
    a = assess_name(name)
    rows = []

    def add(label, new_name, portfolio, turnover):
        r = check(new_name, portfolio)
        rows.append({"option": label, "name": new_name, "exclusions": r.exclusions or "-",
                     "turnover_pct": round(turnover, 1), "compliant": r.compliant,
                     "remaining_issues": "; ".join(r.issues) or "-"})

    add("keep name and portfolio", name, pf, 0)
    if a.exclusions:
        sold = divest(pf, a.exclusions)
        add(f"keep name, sell {a.exclusions} breaches", name, sold, 100 - pf[pf["issuer"].isin(sold["issuer"])]["weight"].sum())
    others = set(a.terms) - {"sustainability"}
    if "sustainability" in a.terms and others:
        add("drop the sustainability term", _remove_terms(name, a.terms["sustainability"]), pf, 0)
    if a.exclusions == "PAB" and not ({"impact", "sustainability"} & set(a.terms)) and "environmental" in a.terms:
        new = name if "transition" in a.terms else _remove_terms(name, a.terms["environmental"], "Transition")
        if "transition" in a.terms:
            new = _remove_terms(name, a.terms["environmental"])
        add("rename as a transition fund (CTB exclusions)", new, pf, 0)
    if a.in_scope:
        rows.append({"option": "remove all ESG terms (out of scope)",
                     "name": _remove_terms(name, [t for ts in a.terms.values() for t in ts]),
                     "exclusions": "-", "turnover_pct": 0.0, "compliant": True,
                     "remaining_issues": "update prospectus, SFDR disclosures and marketing material"})
    return pd.DataFrame(rows)


def _replace_word(name: str, term: str, replacement: str) -> str:
    import re
    import unicodedata
    plain = "".join(c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c))
    pattern = re.compile(r"\b" + r"[\s\-]".join(map(re.escape, term.split())) + r"\b", re.IGNORECASE)
    m = pattern.search(plain)
    if not m:
        return name
    return name[:m.start()] + replacement + name[m.end():]
