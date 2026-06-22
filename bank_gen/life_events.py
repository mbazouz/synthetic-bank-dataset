"""Transition effects catalogue.

Historically this module held an independent-Bernoulli ``generate_life_events``
that drew unordered one-shot shocks. It has been superseded by the life-trajectory
engine (``trajectory.py``), which walks a chronologically-ordered, age-and-profile
driven Markov chain of *phases*. This module now holds only the tuned **magnitudes**
of each transition (income rule, activity shift, leisure-bias deltas, one-shot
expense ranges, structural deltas), which ``trajectory.py`` imports and applies.

Keeping the constants here preserves the values tuned over many generations and
keeps the trajectory walk (which decides *when* and *in what order*) separate
from the effect sizing (*how big*).

`income_rule` semantics (interpreted by trajectory._new_income):
    "to_target" : jump to the new profile's income_mean * income_range factor
    "grow"      : current_income * factor, capped at new_profile.income_mean * 1.3
    "are"       : current_income * factor   (unemployment benefit ~ 55-70%)
    "scale"     : current_income * factor   (mild, e.g. divorce)
    "recover"   : jeune_actif.income_mean * factor (climb back out of precarity)
    "retraite"  : current_income * factor   (pension replacement rate)
    "keep"      : income unchanged (non-income events: marriage, car/home purchase)
"""
from __future__ import annotations


# Per-transition effect magnitudes. `leisure_delta` is overlaid (multiplied) on
# top of the target profile's own leisure_bias. `one_shot` = (category, lo, hi).
TRANSITION_EFFECTS: dict[str, dict] = {
    # ---- ascending career / wealth ------------------------------------------
    "entree_vie_active": {
        "income_rule": "to_target", "income_range": (0.85, 1.10), "activity": 1.0,
        "leisure_delta": {}, "one_shot": None,
    },
    "ascension_cadre": {
        "income_rule": "grow", "income_range": (1.15, 1.40), "activity": 1.05,
        "leisure_delta": {"restauration": 1.2, "voyages": 1.3, "shopping": 1.2},
        "one_shot": None,
    },
    "ascension_csp": {
        "income_rule": "grow", "income_range": (1.20, 1.50), "activity": 1.10,
        "leisure_delta": {"voyages": 1.4, "shopping": 1.3, "restauration": 1.2},
        "one_shot": None,
    },
    "enrichissement": {
        "income_rule": "grow", "income_range": (1.10, 1.30), "activity": 1.0,
        "leisure_delta": {"voyages": 1.5, "shopping": 1.2}, "one_shot": None,
    },
    "developpement_activite": {
        "income_rule": "grow", "income_range": (1.20, 1.60), "activity": 1.10,
        "leisure_delta": {"voyages": 1.3, "restauration": 1.3}, "one_shot": None,
    },
    # ---- descending: job loss / business failure / precarity ----------------
    "perte_emploi": {
        "income_rule": "are", "income_range": (0.55, 0.70), "activity": 0.80,
        "leisure_delta": {"transport": 0.5, "restauration": 0.4, "voyages": 0.3, "shopping": 0.6},
        "one_shot": None,
    },
    "echec_entreprise": {
        "income_rule": "are", "income_range": (0.40, 0.60), "activity": 0.75,
        "leisure_delta": {"transport": 0.5, "restauration": 0.4, "voyages": 0.3, "shopping": 0.5},
        "one_shot": None,
    },
    "retour_emploi": {
        "income_rule": "recover", "income_range": (0.70, 1.05), "activity": 1.0,
        "leisure_delta": {}, "one_shot": None,
    },
    # ---- family formation (split into a parental-leave dip + recovery) -------
    "naissance_dip": {
        "income_rule": "scale", "income_range": (0.82, 0.92), "activity": 0.90,
        "leisure_delta": {"alimentation": 1.3, "sante": 1.4, "restauration": 0.7, "voyages": 0.4},
        "one_shot": ("famille", 800, 2200), "new_subscription": "creche",
    },
    "naissance_recovery": {
        "income_rule": "keep", "income_range": (1.0, 1.0), "activity": 1.05,
        "leisure_delta": {"alimentation": 1.4, "education": 1.5}, "one_shot": None,
    },
    "mariage": {
        "income_rule": "keep", "income_range": (1.0, 1.0), "activity": 1.05,
        "leisure_delta": {}, "one_shot": ("voyages", 3000, 12000),
    },
    "divorce": {
        "income_rule": "scale", "income_range": (0.85, 0.95), "activity": 0.95,
        "leisure_delta": {}, "one_shot": ("logement", 1500, 6000),
    },
    # ---- big purchases (no profile change; originate a loan + one-shot) ------
    "achat_immobilier": {
        "income_rule": "keep", "income_range": (1.0, 1.0), "activity": 1.0,
        "leisure_delta": {"shopping": 1.2}, "one_shot": ("logement", 8000, 45000),
        "new_loan": "credit_immobilier",
    },
    "achat_voiture": {
        "income_rule": "keep", "income_range": (1.0, 1.0), "activity": 1.0,
        "leisure_delta": {"transport": 1.2}, "one_shot": ("transport", 4000, 28000),
        "new_loan": "credit_auto",
    },
    # ---- retirement ---------------------------------------------------------
    "retraite": {
        "income_rule": "retraite", "income_range": (0.55, 0.75), "activity": 0.85,
        "leisure_delta": {"sante": 1.6, "voyages": 1.2, "transport": 0.8}, "one_shot": None,
    },
    # ---- absorbing terminal states (status gates income & discretionary) ----
    "deces": {
        "income_rule": "keep", "income_range": (1.0, 1.0), "activity": 0.0,
        "leisure_delta": {}, "one_shot": None, "status": "deceased",
    },
    "dormance": {
        "income_rule": "keep", "income_range": (1.0, 1.0), "activity": 0.0,
        "leisure_delta": {}, "one_shot": None, "status": "dormant",
    },
}


def effect_for(name: str) -> dict:
    return TRANSITION_EFFECTS[name]
