"""1) Landscape: which real Luxembourg funds carry ESG terms and which rules apply to them (GLEIF names).
2) Simulation: how often a typical ESG-named portfolio fails, and what keeping the name costs (synthetic data).
"""
from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from name_rules import assess_name
from portfolio_check import check, divest, issuer_universe, random_portfolio

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
ORDER = ["environmental", "sustainability", "impact", "transition", "social", "governance"]


def landscape() -> dict:
    df = pd.read_csv(ROOT / "data" / "gleif_lu_funds_esg_keywords.csv")
    a = df["legal_name"].map(assess_name)
    df["categories"] = a.map(lambda x: "+".join(x.categories))
    df["exclusions"] = a.map(lambda x: x.exclusions)
    df["thematic_to_review"] = a.map(lambda x: ", ".join(x.thematic))
    df["false_friends"] = a.map(lambda x: ", ".join(x.false_friends))
    df["requirements"] = a.map(lambda x: " | ".join(x.requirements))
    df.to_csv(REPORTS / "lu_fund_names_classified.csv", index=False)

    in_scope = df[df["categories"] != ""]
    review = df[(df["categories"] == "") & (df["thematic_to_review"] != "")]
    counts = {c: int(in_scope["categories"].str.contains(c).sum()) for c in ORDER}
    stats = {
        "funds_returned_by_keyword_search": len(df),
        "funds_in_scope": len(in_scope),
        "pab_exclusions": int((in_scope["exclusions"] == "PAB").sum()),
        "ctb_exclusions": int((in_scope["exclusions"] == "CTB").sum()),
        "thematic_names_to_review": len(review),
        "false_friends_avoided": int((df["false_friends"] != "").sum()),
        "funds_with_several_categories": int(in_scope["categories"].str.contains(r"\+").sum()),
        "by_category": counts,
    }

    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8), gridspec_kw={"width_ratios": [2, 1]})
    s = pd.Series(counts)[::-1]
    s.plot.barh(ax=axes[0], color="#2E7D5B")
    axes[0].bar_label(axes[0].containers[0], padding=3)
    axes[0].set_title("Luxembourg funds by ESMA term category (real GLEIF names)")
    ex = pd.Series({"PAB exclusions\n(strict)": stats["pab_exclusions"], "CTB exclusions": stats["ctb_exclusions"]})
    ex.plot.bar(ax=axes[1], color=["#C0392B", "#E8A33A"], rot=0)
    axes[1].bar_label(axes[1].containers[0], padding=3)
    axes[1].set_title("Exclusion list triggered by the name")
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_ylabel("")
    axes[0].set_xlim(0, s.max() * 1.15)
    axes[1].set_ylim(0, ex.max() * 1.15)
    plt.tight_layout()
    plt.savefig(REPORTS / "lu_landscape.png", dpi=150)
    return stats


DEMO_NAMES = {  # invented names, one per category
    "environmental": "Demo Global Climate Equity Fund",
    "sustainability": "Demo European Sustainable Equity Fund",
    "impact": "Demo Positive Impact Equity Fund",
    "transition": "Demo Net Zero Transition Equity Fund",
    "social": "Demo Social Bond Fund",
}


def simulation(n: int = 400, seed: int = 11) -> pd.DataFrame:
    universe = issuer_universe()
    rng = np.random.default_rng(seed)
    rows = []
    for cat, name in DEMO_NAMES.items():
        for _ in range(n):
            prefer = {"impact": "impact_kpi", "transition": "transition_plan",
                      "sustainability": "sustainable_investment"}.get(cat)
            pf = random_portfolio(universe, rng, tilt=rng.uniform(1.0, 4.0), prefer=prefer)
            r = check(name, pf)
            sold = divest(pf, r.exclusions)
            after = check(name, sold)
            rows.append({"category": cat, "compliant_as_is": r.compliant, "breach_exclusions": len(r.breaches) > 0,
                         "below_80": r.aligned_pct < 80, "turnover_to_fix_exclusions": r.weight_to_divest,
                         "compliant_after_selling": after.compliant})
    sim = pd.DataFrame(rows)
    table = sim.groupby("category").agg(
        failing_as_is_pct=("compliant_as_is", lambda s: 100 * (1 - s.mean())),
        breach_exclusions_pct=("breach_exclusions", lambda s: 100 * s.mean()),
        below_80_pct=("below_80", lambda s: 100 * s.mean()),
        median_turnover_pct=("turnover_to_fix_exclusions", "median"),
        still_failing_after_selling_pct=("compliant_after_selling", lambda s: 100 * (1 - s.mean())),
    ).round(1).reindex(DEMO_NAMES)
    table.to_csv(REPORTS / "simulation_by_category.csv")
    return table


def main():
    REPORTS.mkdir(exist_ok=True)
    stats = landscape()
    table = simulation()
    (REPORTS / "summary.json").write_text(json.dumps({"landscape": stats,
                                                      "simulation": table.reset_index().to_dict("records")}, indent=2))
    print(json.dumps(stats, indent=2))
    print(table.to_string())


if __name__ == "__main__":
    main()
