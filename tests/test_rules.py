import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from name_rules import assess_name  # noqa: E402
from portfolio_check import breaches, check, divest, issuer_universe, options, random_portfolio  # noqa: E402


@pytest.mark.parametrize("name, cats, excl", [
    ("AMUNDI MSCI EMU SRI CLIMATE PARIS ALIGNED", ["environmental"], "PAB"),
    ("ALLIANZ CLIMATE TRANSITION EUROPE", ["environmental", "transition"], "CTB"),   # combination rule
    ("JSS SUSTAINABLE EQUITY - USA", ["sustainability"], "PAB"),
    ("SOCIAL BOND FUND", ["social"], "CTB"),
    ("POSITIVE IMPACT EMERGING EQUITY", ["impact"], "PAB"),
    ("Green Sustainable Transition Fund", ["environmental", "sustainability", "transition"], "PAB"),
    ("BNP PARIBAS EQUITY EUROPE", [], None),       # false friend
    ("Greenhill Partners Fund", [], None),
    ("Robeco Circular Economy", [], None),
    ("Fonds Durable Actions Europe", ["sustainability"], "PAB"),
    ("Nachhaltigkeit Aktien Global", ["sustainability"], "PAB"),
])
def test_name_classification(name, cats, excl):
    a = assess_name(name)
    assert a.categories == cats
    assert a.exclusions == excl


def test_thematic_flagged_not_in_scope():
    a = assess_name("Global Water Solutions Fund")
    assert not a.in_scope and a.thematic == ["water"]


def test_requirements_for_impact():
    assert any("measurable" in r for r in assess_name("Impact Fund").requirements)


@pytest.fixture(scope="module")
def portfolio():
    return random_portfolio(issuer_universe(), np.random.default_rng(3), tilt=0.0)


def test_pab_stricter_than_ctb(portfolio):
    assert len(breaches(portfolio, "PAB")) >= len(breaches(portfolio, "CTB"))


def test_divest_removes_breaches_and_keeps_100(portfolio):
    sold = divest(portfolio, "PAB")
    assert len(breaches(sold, "PAB")) == 0
    assert sold["weight"].sum() == pytest.approx(100)


def test_out_of_scope_name_is_compliant(portfolio):
    assert check("Global Equity Fund", portfolio).compliant


def test_options_always_offer_leaving_scope(portfolio):
    opts = options("Demo Global Climate Equity Fund", portfolio)
    assert opts.iloc[-1]["name"] == "Demo Global Equity Fund"
    assert opts.iloc[-1]["compliant"]
