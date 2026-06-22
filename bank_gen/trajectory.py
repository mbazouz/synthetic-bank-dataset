"""Life-trajectory engine.

A customer is no longer a single static profile for the whole window. Instead we
build a **trajectory**: a chronologically-ordered, contiguous list of `LifePhase`s.
Each phase binds an active profile archetype, an absolute monthly income, an
activity level, an effective leisure bias, and a status (active / dormant /
deceased). Phases are produced by walking an age-and-profile-driven Markov chain
of transitions (career ascension, job loss + recovery, family formation, big
purchases, retirement, death/dormancy) — NOT by independent Bernoulli draws — so
the sequence is logically ordered (e.g. divorce only after marriage, retirement
age-gated, death terminal).

The transaction engine (`transactions.py`) walks this trajectory day by day,
re-binding behaviour as it crosses phase boundaries. The magnitudes of each
transition live in `life_events.TRANSITION_EFFECTS`; this module owns *when* and
*in what order* transitions happen.

Determinism: all randomness comes from the per-customer `rng`/`rng_np` passed in,
consumed in a fixed order.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from .locales import BankPresetSpec as BankPreset
from .customers import Customer
from .life_events import TRANSITION_EFFECTS
from .profiles import PROFILES


@dataclass
class LifePhase:
    start: date
    end: date                         # = start of the next phase (last = window end)
    profile_name: str                 # active ProfileSpec key for this phase
    monthly_income: float             # ABSOLUTE euros (engine applies inflation on top)
    status: str                       # "active" | "dormant" | "deceased"
    leisure_bias: dict[str, float]    # effective bias (target profile + transition delta)
    activity_multiplier: float
    transition: str                   # "init" | "ascension_cadre" | "perte_emploi" | ...
    one_shot: tuple[str, float] | None = None
    new_loan: str | None = None           # loan type to originate at phase.start
    new_subscription: str | None = None   # subscription to add at phase.start


@dataclass
class Trajectory:
    customer_id: str
    phases: list[LifePhase]           # ordered, contiguous, non-overlapping
    final_children: int               # children at end of trajectory
    final_situation: str              # family situation at end of trajectory


@dataclass(frozen=True)
class TransitionRule:
    name: str                         # key into TRANSITION_EFFECTS
    target: str | None                # new profile, or None to keep current
    base_weight: float
    age_min: int
    age_max: int
    requires_married: bool = False
    requires_not_married: bool = False
    absorbing: bool = False
    prop_key: str = ""                # key into preset.transition_propensity


# Per-profile allowed transitions. Career ascension changes the active profile;
# purchases/marriage/divorce/birth keep it (target=None) but still open a phase.
TRANSITIONS: dict[str, list[TransitionRule]] = {
    "etudiant": [
        TransitionRule("entree_vie_active", "jeune_actif", 6.0, 21, 30, prop_key="ascension"),
        TransitionRule("achat_voiture", None, 0.8, 20, 30, prop_key="achat"),
    ],
    "jeune_actif": [
        TransitionRule("ascension_cadre", "cadre", 3.0, 27, 48, prop_key="ascension"),
        TransitionRule("naissance", None, 3.0, 26, 42, prop_key="naissance"),
        TransitionRule("perte_emploi", "fragile", 1.2, 24, 60, prop_key="perte_emploi"),
        TransitionRule("mariage", None, 1.5, 26, 45, requires_not_married=True, prop_key="naissance"),
        TransitionRule("achat_immobilier", None, 1.2, 28, 50, prop_key="achat"),
        TransitionRule("achat_voiture", None, 1.5, 24, 55, prop_key="achat"),
    ],
    "famille": [
        TransitionRule("ascension_cadre", "cadre", 2.0, 30, 50, prop_key="ascension"),
        TransitionRule("naissance", None, 1.8, 28, 44, prop_key="naissance"),
        TransitionRule("perte_emploi", "fragile", 1.0, 30, 58, prop_key="perte_emploi"),
        TransitionRule("divorce", None, 1.0, 30, 55, requires_married=True, prop_key="divorce"),
        TransitionRule("achat_immobilier", None, 1.6, 30, 52, prop_key="achat"),
        TransitionRule("achat_voiture", None, 1.2, 30, 58, prop_key="achat"),
    ],
    "cadre": [
        TransitionRule("ascension_csp", "csp_plus", 1.6, 33, 57, prop_key="ascension"),
        TransitionRule("naissance", None, 1.5, 30, 45, prop_key="naissance"),
        TransitionRule("perte_emploi", "fragile", 0.7, 30, 58, prop_key="perte_emploi"),
        TransitionRule("achat_immobilier", None, 1.8, 32, 55, prop_key="achat"),
        TransitionRule("achat_voiture", None, 1.3, 30, 60, prop_key="achat"),
        TransitionRule("divorce", None, 0.8, 33, 58, requires_married=True, prop_key="divorce"),
    ],
    "csp_plus": [
        TransitionRule("enrichissement", "investisseur", 1.0, 40, 65, prop_key="enrichissement"),
        TransitionRule("achat_immobilier", None, 1.5, 38, 62, prop_key="achat"),
        TransitionRule("naissance", None, 0.6, 35, 45, prop_key="naissance"),
        TransitionRule("perte_emploi", "fragile", 0.4, 35, 60, prop_key="perte_emploi"),
    ],
    "freelance": [
        TransitionRule("developpement_activite", "entrepreneur", 1.2, 28, 55, prop_key="ascension"),
        TransitionRule("perte_emploi", "fragile", 1.5, 25, 60, prop_key="perte_emploi"),
        TransitionRule("naissance", None, 1.2, 26, 44, prop_key="naissance"),
        TransitionRule("achat_immobilier", None, 0.8, 30, 55, prop_key="achat"),
        TransitionRule("achat_voiture", None, 1.2, 25, 58, prop_key="achat"),
    ],
    "entrepreneur": [
        TransitionRule("enrichissement", "csp_plus", 1.0, 33, 60, prop_key="enrichissement"),
        TransitionRule("echec_entreprise", "fragile", 1.0, 30, 60, prop_key="perte_emploi"),
        TransitionRule("achat_immobilier", None, 1.2, 33, 60, prop_key="achat"),
    ],
    "investisseur": [
        TransitionRule("achat_immobilier", None, 1.5, 38, 70, prop_key="achat"),
        TransitionRule("enrichissement", None, 0.8, 40, 70, prop_key="enrichissement"),
    ],
    "fragile": [
        TransitionRule("retour_emploi", "jeune_actif", 1.5, 22, 58, prop_key="ascension"),
        TransitionRule("naissance", None, 0.7, 24, 42, prop_key="naissance"),
    ],
    "retraite": [],  # only universal transitions (death / dormancy) below
}

# Universal (non-terminal) transition. Death/dormancy are NOT rules — they are
# per-step Bernoulli draws (see _death_prob / _dormancy_prob).
RETRAITE_RULE = TransitionRule("retraite", "retraite", 2.0, 60, 120, prop_key="retraite")

# Tuning knobs
MIN_SPAN_FOR_TRANSITIONS = 150     # days; below this the customer stays single-phase
FIRST_GAP_DAYS = (180, 540)        # delay before the first possible transition
GAP_MONTHS = (12, 48)              # spacing between successive transitions
NAISSANCE_DIP_MONTHS = (4, 7)      # parental-leave dip duration
MAX_PHASES = 7
MIN_TAIL_DAYS = 45                 # don't open a phase right at the window end
# Weight of the "no transition this step" option = max(STAY_BIAS * sum(weights),
# STAY_FLOOR). The floor is essential: without it, a customer whose only candidate
# is a tiny-weight terminal event (e.g. a retiree with just death/dormancy options)
# would pick that event ~50% of the time, wildly inflating dormancy/death.
STAY_BIAS = 1.1
STAY_FLOOR = 3.0


def _age_at(customer: Customer, d: date) -> int:
    return (d - customer.date_naissance).days // 365


def _months_to_days(months: int) -> int:
    return int(months * 30.4)


def _effective_leisure(profile_name: str, delta: dict[str, float]) -> dict[str, float]:
    base = dict(PROFILES[profile_name].leisure_bias)
    for k, v in delta.items():
        base[k] = base.get(k, 1.0) * v
    return base


def _sample_one_shot(eff: dict, rng: random.Random) -> tuple[str, float] | None:
    one = eff.get("one_shot")
    if not one:
        return None
    cat, lo, hi = one
    return (cat, round(rng.uniform(lo, hi), 2))


def _new_income(eff: dict, cur_income: float, target_profile: str | None, rng: random.Random) -> float:
    lo, hi = eff["income_range"]
    f = rng.uniform(lo, hi)
    rule = eff["income_rule"]
    if rule == "to_target":
        tm = PROFILES[target_profile].income_mean if target_profile else cur_income
        return max(cur_income, tm * f)
    if rule == "grow":
        tm = PROFILES[target_profile].income_mean if target_profile else cur_income * 1.5
        return min(cur_income * f, tm * 1.3)
    if rule in ("are", "scale", "retraite"):
        return cur_income * f
    if rule == "recover":
        return PROFILES["jeune_actif"].income_mean * f
    return cur_income  # "keep"


def _death_prob(age: int, preset: BankPreset) -> float:
    """Per-step probability of death. Independent of available transitions so it
    keeps firing for old retirees who have no other moves left."""
    if age < 55:
        p = 0.0
    elif age < 70:
        p = 0.03
    elif age < 80:
        p = 0.10
    else:
        p = 0.22
    return min(0.9, p * preset.mortality_scale)


def _dormancy_prob(preset: BankPreset) -> float:
    """Per-step probability of account abandonment (compounds over ~3-4 steps to
    ~10% for a normal bank, ~25% for a churn-prone neobank)."""
    return min(0.9, 0.025 * preset.dormancy_scale)


def _candidate_transitions(
    profile: str, age: int, married: bool, preset: BankPreset,
) -> tuple[list[TransitionRule], list[float]]:
    """Non-terminal transitions only. Death/dormancy are handled separately as
    per-step Bernoulli draws (see generate_trajectory) so their rate doesn't
    depend on how many ordinary transitions happen to be available."""
    rules: list[TransitionRule] = []
    weights: list[float] = []
    for rule in TRANSITIONS.get(profile, []):
        if not (rule.age_min <= age <= rule.age_max):
            continue
        if rule.requires_married and not married:
            continue
        if rule.requires_not_married and married:
            continue
        w = rule.base_weight * preset.transition_propensity.get(rule.prop_key, 1.0)
        if w > 0:
            rules.append(rule)
            weights.append(w)
    # Universal (non-terminal) transition: retirement, age-gated.
    if profile != "retraite" and age >= RETRAITE_RULE.age_min:
        w = RETRAITE_RULE.base_weight * preset.transition_propensity.get("retraite", 1.0)
        if w > 0:
            rules.append(RETRAITE_RULE)
            weights.append(w)
    return rules, weights


def _terminal_phase(name: str, cursor: date, end: date, profile: str, income: float) -> LifePhase:
    eff = TRANSITION_EFFECTS[name]
    return LifePhase(
        start=cursor, end=end, profile_name=profile, monthly_income=round(income, 2),
        status=eff["status"], leisure_bias={}, activity_multiplier=0.0, transition=name,
    )


def _make_naissance_phases(
    cursor: date, end: date, cur_profile: str, cur_income: float, rng: random.Random,
) -> list[LifePhase]:
    dip_eff = TRANSITION_EFFECTS["naissance_dip"]
    rec_eff = TRANSITION_EFFECTS["naissance_recovery"]
    dip_income = round(cur_income * rng.uniform(*dip_eff["income_range"]), 2)
    phases = [LifePhase(
        start=cursor, end=end, profile_name=cur_profile,
        monthly_income=dip_income, status="active",
        leisure_bias=_effective_leisure(cur_profile, dip_eff["leisure_delta"]),
        activity_multiplier=dip_eff["activity"], transition="naissance",
        one_shot=_sample_one_shot(dip_eff, rng),
        new_subscription=dip_eff.get("new_subscription"),
    )]
    rec_start = cursor + timedelta(days=_months_to_days(rng.randint(*NAISSANCE_DIP_MONTHS)))
    if rec_start < end - timedelta(days=MIN_TAIL_DAYS):
        phases.append(LifePhase(
            start=rec_start, end=end, profile_name=cur_profile,
            monthly_income=round(cur_income, 2), status="active",
            leisure_bias=_effective_leisure(cur_profile, rec_eff["leisure_delta"]),
            activity_multiplier=rec_eff["activity"], transition="naissance_recovery",
        ))
    return phases


def _seal(customer: Customer, phases: list[LifePhase], end: date,
          children: int, situation: str) -> Trajectory:
    phases.sort(key=lambda p: p.start)
    for i in range(len(phases) - 1):
        phases[i].end = phases[i + 1].start
    phases[-1].end = end
    return Trajectory(customer.customer_id, phases, children, situation)


def generate_trajectory(
    customer: Customer,
    start: date,
    end: date,
    preset: BankPreset,
    rng: random.Random,
    rng_np: np.random.Generator,
) -> Trajectory:
    """Build the ordered phase list for a customer over [start, end].

    `start` must be the customer's effective window start (post bank-entry clamp).
    """
    profile0 = PROFILES[customer.profil]
    age0 = _age_at(customer, start)
    cur_profile = customer.profil
    cur_income = customer.revenu_mensuel
    children = customer.nombre_enfants
    situation = customer.situation_familiale
    married = situation in ("marie", "pacse")

    # Phase 0 always matches the representative archetype (invariant).
    phases: list[LifePhase] = [LifePhase(
        start=start, end=end, profile_name=cur_profile, monthly_income=cur_income,
        status="active", leisure_bias=dict(profile0.leisure_bias),
        activity_multiplier=1.0, transition="init",
    )]

    if (end - start).days < MIN_SPAN_FOR_TRANSITIONS:
        return _seal(customer, phases, end, children, situation)

    cursor = start + timedelta(days=rng.randint(*FIRST_GAP_DAYS))
    while cursor < end - timedelta(days=MIN_TAIL_DAYS):
        age = age0 + (cursor - start).days // 365
        # Terminal events: independent per-step Bernoulli, evaluated every step
        # (even when no ordinary transition is available, so old retirees still die).
        if rng.random() < _death_prob(age, preset):
            phases.append(_terminal_phase("deces", cursor, end, cur_profile, cur_income))
            break
        if rng.random() < _dormancy_prob(preset):
            phases.append(_terminal_phase("dormance", cursor, end, cur_profile, cur_income))
            break

        gap = timedelta(days=_months_to_days(rng.randint(*GAP_MONTHS)))
        rules, weights = _candidate_transitions(cur_profile, age, married, preset)
        if not rules or len(phases) >= MAX_PHASES:
            cursor += gap
            continue
        stay_w = max(STAY_BIAS * sum(weights), STAY_FLOOR)
        idx = rng.choices(range(len(rules) + 1), weights=weights + [stay_w], k=1)[0]
        if idx == len(rules):  # "stay" — no transition this step
            cursor += gap
            continue
        chosen = rules[idx]

        if chosen.name == "naissance":
            new_phases = _make_naissance_phases(cursor, end, cur_profile, cur_income, rng)
            phases.extend(new_phases)
            children += 1
            if not married and rng.random() < 0.5:
                married, situation = True, "marie"
            cursor = new_phases[-1].start + gap
            continue

        eff = TRANSITION_EFFECTS[chosen.name]
        target = chosen.target or cur_profile
        new_income = _new_income(eff, cur_income, chosen.target, rng)
        phases.append(LifePhase(
            start=cursor, end=end, profile_name=target,
            monthly_income=round(new_income, 2), status="active",
            leisure_bias=_effective_leisure(target, eff["leisure_delta"]),
            activity_multiplier=eff["activity"], transition=chosen.name,
            one_shot=_sample_one_shot(eff, rng),
            new_loan=eff.get("new_loan"), new_subscription=eff.get("new_subscription"),
        ))
        cur_profile = target
        cur_income = new_income
        if chosen.name == "mariage":
            married, situation = True, "marie"
        elif chosen.name == "divorce":
            married, situation = False, "divorce"
        cursor += gap

    return _seal(customer, phases, end, children, situation)
