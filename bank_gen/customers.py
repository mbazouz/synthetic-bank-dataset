"""Customer generation.

Each customer carries enough state for the downstream transaction engine to
build a coherent banking history: profile, sampled income, family situation,
appetite for risk, etc.
"""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from datetime import date, timedelta

import numpy as np
from faker import Faker

from .config import PROFILE_DISTRIBUTION
from .locales import (
    LOCALE_SALT,
    MIX_CODES,
    MIX_WEIGHTS,
    BankPresetSpec,
    Locale,
    get_locale,
)
from .profiles import PROFILES, ProfileSpec


@dataclass
class Customer:
    customer_id: str
    prenom: str
    nom: str
    sexe: str
    age: int
    date_naissance: date
    ville: str
    code_postal: str
    pays: str
    locale_code: str
    situation_familiale: str
    nombre_enfants: int
    profession: str
    segment_client: str
    profil: str
    bank_preset: str
    revenu_mensuel: float
    patrimoine_estime: float
    score_financier: int
    appetence_risque: str
    date_entree_banque: date

    def to_row(self) -> dict:
        # Emit English column names; localize taxonomy VALUES for output (the
        # in-memory object keeps canonical/French tokens so downstream logic is
        # unaffected). The raw column NAMES are English; the internal attribute
        # names stay French.
        loc = get_locale(self.locale_code)
        return {
            "customer_id": self.customer_id,
            "first_name": self.prenom,
            "last_name": self.nom,
            "sex": self.sexe,
            "age": self.age,
            "birth_date": self.date_naissance.isoformat(),
            "city": self.ville,
            "postal_code": self.code_postal,
            "country": self.pays,
            "locale_code": self.locale_code,
            "family_situation": loc.cust_family(self.situation_familiale),
            "num_children": self.nombre_enfants,
            "profession": self.profession,
            "customer_segment": loc.cust_segment(self.segment_client),
            "profile": loc.cust_profil(self.profil),
            "bank_preset": self.bank_preset,
            "monthly_income": self.revenu_mensuel,
            "estimated_wealth": self.patrimoine_estime,
            "financial_score": self.score_financier,
            "risk_appetite": loc.cust_risk(self.appetence_risque),
            "customer_since": self.date_entree_banque.isoformat(),
        }


SEGMENT_MAP = {
    "etudiant":     "JEUNE",
    "jeune_actif":  "STANDARD",
    "famille":      "STANDARD",
    "cadre":        "PREMIUM",
    "csp_plus":     "PRIVATE",
    "freelance":    "PRO",
    "entrepreneur": "PRO_PREMIUM",
    "investisseur": "PRIVATE",
    "retraite":     "SENIOR",
    "fragile":      "FRAGILE",
}


def _weighted_choice(items: list, weights: list[float], rng: random.Random):
    return rng.choices(items, weights=weights, k=1)[0]


def _sample_city(cities, rng: random.Random):
    weights = [c[1] for c in cities]
    return _weighted_choice(list(cities), weights, rng)


# Canonical family-situation tokens (French); locales translate them at output.
_CANONICAL_FAMILY = ("celibataire", "marie", "pacse", "concubinage", "divorce", "veuf")


def _sample_family_situation(profile: str, age: int, rng: random.Random) -> tuple[str, int]:
    if profile == "etudiant" or age < 24:
        situ = rng.choices(["celibataire", "concubinage"], weights=[0.85, 0.15])[0]
        kids = 0 if situ == "celibataire" else rng.choices([0, 1], weights=[0.95, 0.05])[0]
    elif profile == "famille":
        situ = rng.choices(["marie", "pacse", "concubinage", "divorce"], weights=[0.55, 0.20, 0.15, 0.10])[0]
        kids = rng.choices([1, 2, 3, 4], weights=[0.30, 0.45, 0.20, 0.05])[0]
    elif profile == "retraite":
        situ = rng.choices(["marie", "veuf", "divorce", "celibataire"], weights=[0.55, 0.20, 0.15, 0.10])[0]
        kids = rng.choices([0, 1, 2, 3], weights=[0.15, 0.25, 0.40, 0.20])[0]
    elif profile in ("csp_plus", "cadre", "investisseur"):
        situ = rng.choices(["marie", "pacse", "celibataire", "divorce"], weights=[0.50, 0.20, 0.20, 0.10])[0]
        kids = rng.choices([0, 1, 2, 3], weights=[0.25, 0.30, 0.35, 0.10])[0]
    else:
        situ = rng.choice(_CANONICAL_FAMILY)
        kids = rng.choices([0, 1, 2], weights=[0.55, 0.25, 0.20])[0]
    return situ, kids


def _financial_score(profile: ProfileSpec, revenu: float, patrimoine: float, rng: random.Random) -> int:
    base = {
        "etudiant": 540, "jeune_actif": 640, "famille": 670, "cadre": 720,
        "csp_plus": 780, "freelance": 660, "entrepreneur": 700, "investisseur": 790,
        "retraite": 700, "fragile": 480,
    }[profile.name]
    base += int(np.clip((revenu - profile.income_mean) / max(profile.income_mean, 1) * 35, -80, 80))
    base += int(np.clip(np.log1p(patrimoine) * 4, 0, 60))
    base += rng.randint(-20, 20)
    return int(np.clip(base, 300, 900))


def _distribution_arrays(distribution: dict[str, float]) -> tuple[list[str], list[float]]:
    items, weights = zip(*distribution.items())
    return list(items), list(weights)


def generate_customers(
    n: int,
    seed: int,
    presets: dict[str, BankPresetSpec] | None = None,
    preset_weights: dict[str, float] | None = None,
    country: str = "us",
) -> list[Customer]:
    """Generate customers.

    When `presets` is given, each customer is first assigned a bank preset (per
    `preset_weights`, equal-weighted by default) and then its profile is sampled
    from that preset's distribution — so different banks get different mixes.
    When `presets` is None, the global `PROFILE_DISTRIBUTION` is used and
    `bank_preset` is left empty (accounts fall back to a random bank).

    `country` is one of fr|us|uk|mix. With `mix`, each customer is assigned a
    country (per MIX_WEIGHTS) from the shared customer-loop RNG, so the
    assignment is deterministic; names are drawn from one independently-seeded
    Faker per locale to keep the streams reproducible and non-interleaved.
    """
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed + 1)

    locale_codes = list(MIX_CODES) if country == "mix" else [country]
    fakers: dict[str, Faker] = {}
    for code in locale_codes:
        f = Faker(get_locale(code).faker_locale)
        f.seed_instance(seed + 2 + LOCALE_SALT[code])
        fakers[code] = f

    if presets:
        preset_ids = list(presets.keys())
        pweights = [(preset_weights or {}).get(pid, 1.0) for pid in preset_ids]
        profile_arrays = {pid: _distribution_arrays(presets[pid].distribution) for pid in preset_ids}
    else:
        preset_ids = None
        global_names, global_weights = _distribution_arrays(PROFILE_DISTRIBUTION)

    today = date.today()
    customers: list[Customer] = []
    for i in range(n):
        # Assign the customer's locale FIRST (only consumes RNG in mix mode), so
        # downstream draws stay aligned with single-country mode.
        code = rng.choices(MIX_CODES, weights=MIX_WEIGHTS, k=1)[0] if country == "mix" else country
        loc = get_locale(code)
        fake = fakers[code]
        gender_names = [g[0] for g in loc.gender_dist]
        gender_weights = [g[1] for g in loc.gender_dist]

        if preset_ids:
            bank_preset = rng.choices(preset_ids, weights=pweights, k=1)[0]
            names, weights = profile_arrays[bank_preset]
            profile_name = rng.choices(names, weights=weights, k=1)[0]
        else:
            bank_preset = ""
            profile_name = rng.choices(global_names, weights=global_weights, k=1)[0]
        profile = PROFILES[profile_name]
        sex = rng.choices(gender_names, weights=gender_weights, k=1)[0]
        age = rng.randint(*profile.age_range)
        # birthdate within the year
        birthdate = today - timedelta(days=age * 365 + rng.randint(0, 364))
        first = fake.first_name_female() if sex == "F" else fake.first_name_male()
        last = fake.last_name()
        city, _, region = _sample_city(loc.cities, rng)
        cp = loc.postal_for_region(region, rng)
        situ, kids = _sample_family_situation(profile_name, age, rng)
        profession = rng.choice(list(loc.professions[profile_name]))

        # revenue sampling (truncated normal), scaled to the locale's currency level
        inc_mean = profile.income_mean * loc.income_scale
        inc_std = profile.income_std * loc.income_scale
        revenu = float(np.clip(np_rng.normal(inc_mean, inc_std),
                               inc_mean * 0.4, inc_mean * 3.5))
        # wealth multiple
        lo, hi = profile.wealth_multiple
        patrimoine = float(revenu * np_rng.uniform(lo, hi))
        # Investor and CSP+ skew the upper tail
        if profile_name in ("investisseur", "csp_plus") and np_rng.random() < 0.3:
            patrimoine *= np_rng.uniform(2, 6)
        score = _financial_score(profile, revenu, patrimoine, rng)
        # date d'entrée en banque: 0 to 30 ans avant aujourd'hui, plafonnée à age - 18
        years_with_bank = min(age - 18, rng.randint(0, 30)) if age > 18 else 1
        entry = today - timedelta(days=years_with_bank * 365 + rng.randint(0, 364))

        customers.append(Customer(
            customer_id=f"C{i+1:07d}",
            prenom=first,
            nom=last,
            sexe=sex,
            age=age,
            date_naissance=birthdate,
            ville=city,
            code_postal=cp,
            pays=loc.country_name,
            locale_code=code,
            situation_familiale=situ,
            nombre_enfants=kids,
            profession=profession,
            segment_client=SEGMENT_MAP[profile_name],
            profil=profile_name,
            bank_preset=bank_preset,
            revenu_mensuel=round(revenu, 2),
            patrimoine_estime=round(patrimoine, 2),
            score_financier=score,
            appetence_risque=profile.risk_appetite,
            date_entree_banque=entry,
        ))
    return customers
