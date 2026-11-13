"""Draft a short note for the fund's board / conducting officers from the check results.

With ANTHROPIC_API_KEY set, Claude writes the note from the computed figures only.
Without a key, a template is used. Figures and compliance status always come from the rule engine.
"""
import os

import pandas as pd

from portfolio_check import CheckResult


def template_memo(r: CheckResult, opts: pd.DataFrame, lang: str = "en") -> str:
    fixes = opts[opts["compliant"]]
    if lang == "fr":
        head = (f"Fonds : {r.name}\nCatégories ESMA détectées dans le nom : {', '.join(r.categories) or 'aucune'}"
                f"\nExclusions applicables : {r.exclusions or 'aucune'}\n")
        status = "Conforme." if r.compliant else "Non conforme :\n- " + "\n- ".join(r.issues)
        opt = "\n".join(f"- {o['option']} → « {o['name']} » (rotation {o['turnover_pct']} %)" for _, o in fixes.iterrows())
        return f"{head}\nStatut : {status}\n\nOptions qui rendent le fonds conforme :\n{opt}"
    head = (f"Fund: {r.name}\nESMA categories found in the name: {', '.join(r.categories) or 'none'}"
            f"\nExclusions that apply: {r.exclusions or 'none'}\n")
    status = "Compliant." if r.compliant else "Not compliant:\n- " + "\n- ".join(r.issues)
    opt = "\n".join(f"- {o['option']} → \"{o['name']}\" (turnover {o['turnover_pct']}%)" for _, o in fixes.iterrows())
    return f"{head}\nStatus: {status}\n\nOptions that make the fund compliant:\n{opt}"


def memo(r: CheckResult, opts: pd.DataFrame, lang: str = "en") -> tuple[str, str]:
    base = template_memo(r, opts, lang)
    if not os.getenv("ANTHROPIC_API_KEY"):
        return base, "template"
    try:
        import anthropic

        language = "French" if lang == "fr" else "English"
        prompt = (f"You are a compliance analyst in a Luxembourg management company. Using ONLY the facts below, "
                  f"write a note of at most 180 words in {language} to the conducting officers: the issue, the "
                  f"options with their cost (turnover), and a recommendation with its trade-off. Do not invent "
                  f"figures. Plain text, no markdown.\n\nFACTS:\n{base}\n\nAll options:\n{opts.to_string()}")
        msg = anthropic.Anthropic().messages.create(
            model=os.getenv("MEMO_MODEL", "claude-haiku-4-5-20251001"), max_tokens=400,
            messages=[{"role": "user", "content": prompt}])
        return msg.content[0].text.strip(), "claude"
    except Exception:
        return base, "template"
