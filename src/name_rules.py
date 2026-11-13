"""Classify a fund name under the ESMA Guidelines on funds' names using ESG or sustainability-related terms
(ESMA34-1592494965-657, final report 14 May 2024; new funds from 21 Nov 2024, existing funds from 21 May 2025)
and derive the minimum requirements the portfolio must meet.

Summary of the guidelines:
- every category: at least 80% of investments used to meet the E/S characteristics or sustainable objectives;
- environmental-, impact- and sustainability-related terms: Paris-aligned Benchmark (PAB) exclusions;
- transition-, social- and governance-related terms: Climate Transition Benchmark (CTB) exclusions;
- transition terms: investments on a clear and measurable path to transition;
- impact terms: objective of positive, measurable social or environmental impact;
- sustainability terms: commit to invest meaningfully in sustainable investments (SFDR art. 2(17));
- environmental + transition terms together: CTB exclusions are enough (unless a sustainability term is used).
"ESG" and "SRI" count as environmental terms.

The term lists are an interpretation for screening. Thematic words (water, solar, clean energy...) are flagged
"to review" because supervisors may treat them as environmental terms.
"""
from dataclasses import dataclass, field
import re
import unicodedata

CATEGORIES = {
    "environmental": [r"esg", r"sri", r"isr", r"green\w*", r"climate", r"environment\w*", r"ecolog\w*", r"eco",
                      r"oko\w*", r"low[ -]carbon", r"carbon[ -](neutral|reduction|reduced|efficient)",
                      r"paris[ -]aligned", r"pab", r"biodiversity", r"nature[ -]positive", r"planet\w*",
                      r"klima\w*", r"umwelt\w*", r"vert(e|s)?", r"verde"],
    "sustainability": [r"sustainab\w*", r"sustain", r"durable\w*", r"nachhaltig\w*", r"sostenibil\w*", r"duurzaam\w*",
                       r"sostenible\w*", r"responsib\w*", r"responsable\w*", r"verantwortung\w*", r"ethic\w*",
                       r"ethique\w*", r"sdg\w*"],
    "impact": [r"impact", r"positive[ -]change", r"positive[ -]impact"],
    "transition": [r"transition\w*", r"net[ -]?zero", r"improv\w*", r"decarboni[sz]\w*", r"transformation",
                   r"brown[ -]to[ -]green", r"ctb"],
    "social": [r"social\w*", r"gender", r"inclusion", r"inclusive", r"equality", r"solidar\w*",
               r"microfinance", r"affordable[ -]housing"],
    "governance": [r"governance", r"gouvernance"],
}
THEMATIC = [r"water", r"solar", r"renewable\w*", r"clean[ -](energy|power|tech\w*|resources)", r"circular",
            r"wind", r"hydrogen", r"electrification", r"energy[ -]efficiency"]
# words that look like ESG terms but are not (brands, cities, surnames)
FALSE_FRIENDS = [r"paribas", r"parvest", r"greenwich", r"greenhill", r"greenoak", r"greenspring", r"greenland",
                 r"paris (office|retail|real estate|residential|logistics|hotel)", r"eco[ -]?nomic\w*",
                 r"econom\w*", r"esg ?(?=data)"]

PAB_RULES = {
    "controversial_weapons": ("any involvement in controversial weapons", "flag"),
    "tobacco": ("involved in the cultivation and production of tobacco", "flag"),
    "ungc_violation": ("violates UN Global Compact principles or OECD Guidelines", "flag"),
    "coal_rev_pct": ("1% or more of revenues from hard coal and lignite", 1.0),
    "oil_rev_pct": ("10% or more of revenues from oil fuels", 10.0),
    "gas_rev_pct": ("50% or more of revenues from gaseous fuels", 50.0),
    "high_ghg_power_rev_pct": ("50% or more of revenues from electricity with GHG intensity > 100 gCO2e/kWh", 50.0),
}
CTB_KEYS = ["controversial_weapons", "tobacco", "ungc_violation"]


def normalise(text: str) -> str:
    text = "".join(c for c in unicodedata.normalize("NFKD", str(text)) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _find(patterns, text):
    return [m.group(0) for p in patterns for m in re.finditer(rf"\b(?:{p})\b", text)]


@dataclass
class NameAssessment:
    name: str
    terms: dict[str, list[str]] = field(default_factory=dict)
    thematic: list[str] = field(default_factory=list)
    false_friends: list[str] = field(default_factory=list)

    @property
    def categories(self) -> list[str]:
        return sorted(self.terms)

    @property
    def in_scope(self) -> bool:
        return bool(self.terms)

    @property
    def exclusions(self) -> str | None:
        c = set(self.terms)
        if not c:
            return None
        if "sustainability" in c or "impact" in c:
            return "PAB"
        if "environmental" in c and "transition" in c:
            return "CTB"          # combination rule
        if "environmental" in c:
            return "PAB"
        return "CTB"

    @property
    def requirements(self) -> list[str]:
        if not self.in_scope:
            return []
        req = ["at least 80% of investments meet the E/S characteristics or sustainable objectives",
               f"apply {self.exclusions} exclusions"]
        if "transition" in self.terms:
            req.append("investments on a clear and measurable path to environmental or social transition")
        if "impact" in self.terms:
            req.append("investments made to generate a positive, measurable social or environmental impact")
        if "sustainability" in self.terms:
            req.append("invest meaningfully in sustainable investments (SFDR article 2(17))")
        return req


def assess_name(name: str) -> NameAssessment:
    text = normalise(name)
    false_friends = _find(FALSE_FRIENDS, text)
    for ff in false_friends:
        text = text.replace(ff, " ")
    terms = {cat: hits for cat, pats in CATEGORIES.items() if (hits := _find(pats, text))}
    return NameAssessment(name, terms, _find(THEMATIC, text), false_friends)
