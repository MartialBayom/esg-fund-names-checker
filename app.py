"""Streamlit demo: run `streamlit run app.py`."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from memo import memo  # noqa: E402
from name_rules import assess_name  # noqa: E402
from portfolio_check import check, issuer_universe, options, random_portfolio  # noqa: E402

ROOT = Path(__file__).parent
st.set_page_config(page_title="ESG fund names checker", page_icon="🌱", layout="wide")
st.title("ESG fund names checker (ESMA guidelines)")

tab1, tab2, tab3 = st.tabs(["1. Check a name", "2. Check a portfolio", "3. Luxembourg landscape"])

with tab1:
    name = st.text_input("Fund name", "Demo European Sustainable Climate Transition Fund")
    a = assess_name(name)
    if a.in_scope:
        st.success(f"In scope. Categories: {', '.join(a.categories)}. Exclusions: {a.exclusions}")
        st.write("Minimum requirements:")
        for r in a.requirements:
            st.write(f"- {r}")
    else:
        st.info("No ESG term found: the guidelines do not apply to this name.")
    if a.thematic:
        st.warning(f"Thematic words to review with compliance: {', '.join(a.thematic)}")
    if a.false_friends:
        st.caption(f"Ignored false friends: {', '.join(a.false_friends)}")

with tab2:
    st.caption("Synthetic portfolio (60 issuers). Issuer data would normally come from an ESG data vendor.")
    c1, c2, c3 = st.columns(3)
    demo_name = c1.text_input("Demo fund name", "Demo Global Climate Equity Fund")
    tilt = c2.slider("How strict is the manager's ESG selection?", 0.0, 5.0, 2.0)
    seed = c3.number_input("Portfolio seed", 0, 9999, 7)
    lang = st.radio("Memo language", ["en", "fr"], horizontal=True)
    pf = random_portfolio(issuer_universe(), np.random.default_rng(int(seed)), tilt=tilt)
    r = check(demo_name, pf)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Aligned with E/S characteristics", f"{r.aligned_pct}%", help="minimum 80%")
    m2.metric("Sustainable investments", f"{r.sustainable_pct}%")
    m3.metric("Weight breaching exclusions", f"{r.weight_to_divest}%")
    m4.metric("Status", "Compliant" if r.compliant else "Not compliant")
    if len(r.breaches):
        st.dataframe(r.breaches, hide_index=True)
    opts = options(demo_name, pf)
    st.subheader("Options")
    st.dataframe(opts, hide_index=True)
    text, source = memo(r, opts, lang)
    st.subheader(f"Note for the conducting officers (written by: {source})")
    st.text(text)

with tab3:
    st.image(str(ROOT / "reports" / "lu_landscape.png"))
    st.dataframe(pd.read_csv(ROOT / "reports" / "simulation_by_category.csv"), hide_index=True)
    df = pd.read_csv(ROOT / "reports" / "lu_fund_names_classified.csv")
    q = st.text_input("Search a real Luxembourg fund name (GLEIF)", "climate")
    st.dataframe(df[df["legal_name"].str.contains(q, case=False, na=False)]
                 [["legal_name", "categories", "exclusions", "requirements"]].head(200), hide_index=True)
