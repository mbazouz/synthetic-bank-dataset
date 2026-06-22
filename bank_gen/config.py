"""Static configuration: banks, cities, profile distribution, inflation, etc."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

DEFAULT_SEED = 4242
# Evergreen window: generate transactions for the ~3 years ending TODAY, not a
# fixed 2022–2024 span. Downstream analytics often evaluate "recent" signals
# with windows anchored on now() (e.g. the last 365 days); a dataset whose
# newest transaction is months in the past leaves every recent-activity feature
# empty. Anchoring on today keeps demos and pipelines live.
DEFAULT_END_DATE = date.today()
DEFAULT_START_DATE = DEFAULT_END_DATE - timedelta(days=365 * 3)
COUNTRY = "FR"
COUNTRY_NAME = "France"
CURRENCY = "EUR"

# French banks (synthetic, fictitious BIC + bank codes)
BANKS = [
    {"name": "Banque Atlas",      "bic": "ATLAFRPPXXX", "bank_code": "30001"},
    {"name": "Crédit Synthétique", "bic": "CRSYFRPPXXX", "bank_code": "30002"},
    {"name": "Banque Hexagone",    "bic": "BHEXFRPPXXX", "bank_code": "30003"},
    {"name": "Néo Bank IDF",       "bic": "NEIDFRPPXXX", "bank_code": "30004"},
]

# Cities with population-weighted likelihood
CITIES_FR = [
    ("Paris", 2_100_000, "75"), ("Marseille", 870_000, "13"), ("Lyon", 520_000, "69"),
    ("Toulouse", 490_000, "31"), ("Nice", 340_000, "06"), ("Nantes", 320_000, "44"),
    ("Montpellier", 295_000, "34"), ("Strasbourg", 285_000, "67"), ("Bordeaux", 260_000, "33"),
    ("Lille", 235_000, "59"), ("Rennes", 220_000, "35"), ("Reims", 180_000, "51"),
    ("Le Havre", 165_000, "76"), ("Saint-Étienne", 170_000, "42"), ("Toulon", 175_000, "83"),
    ("Grenoble", 160_000, "38"), ("Dijon", 160_000, "21"), ("Angers", 155_000, "49"),
    ("Nîmes", 150_000, "30"), ("Villeurbanne", 155_000, "69"), ("Saint-Denis", 115_000, "93"),
    ("Aix-en-Provence", 145_000, "13"), ("Le Mans", 145_000, "72"), ("Clermont-Ferrand", 145_000, "63"),
    ("Brest", 140_000, "29"), ("Tours", 140_000, "37"), ("Amiens", 135_000, "80"),
    ("Limoges", 130_000, "87"), ("Annecy", 130_000, "74"), ("Boulogne-Billancourt", 125_000, "92"),
    ("Perpignan", 120_000, "66"), ("Besançon", 115_000, "25"), ("Metz", 115_000, "57"),
    ("Orléans", 115_000, "45"), ("Rouen", 110_000, "76"), ("Montreuil", 110_000, "93"),
    ("Caen", 105_000, "14"), ("Argenteuil", 110_000, "95"), ("Nancy", 105_000, "54"),
    ("Saint-Paul", 105_000, "974"), ("Roubaix", 100_000, "59"), ("Tourcoing", 100_000, "59"),
    ("Mulhouse", 110_000, "68"), ("Nanterre", 95_000, "92"), ("Vitry-sur-Seine", 95_000, "94"),
    ("Créteil", 92_000, "94"), ("Avignon", 92_000, "84"), ("Poitiers", 90_000, "86"),
    ("Aubervilliers", 89_000, "93"), ("Courbevoie", 85_000, "92"), ("Versailles", 85_000, "78"),
    ("Pau", 78_000, "64"), ("La Rochelle", 77_000, "17"), ("Cannes", 74_000, "06"),
    ("Calais", 72_000, "62"), ("Antibes", 75_000, "06"), ("Mérignac", 72_000, "33"),
]

# Profile distribution (must sum to 1.0). Global fallback when no bank preset
# is selected.
PROFILE_DISTRIBUTION = {
    "etudiant":      0.10,
    "jeune_actif":   0.18,
    "famille":       0.22,
    "cadre":         0.13,
    "csp_plus":      0.06,
    "freelance":     0.07,
    "entrepreneur":  0.03,
    "investisseur":  0.02,
    "retraite":      0.14,
    "fragile":       0.05,
}


# ---------------------------------------------------------------------------
# Bank presets — locale-neutral behavioural archetypes.
# ---------------------------------------------------------------------------
# A preset gives a (synthetic) bank a DISTINCT customer mix AND distinct
# life-trajectory propensities, so two banks no longer look identical ("90%
# stable, no segmentation"). Each customer is assigned one preset; its trajectory
# transitions are scaled by `transition_propensity` / `mortality_scale` /
# `dormancy_scale`. The bank IDENTITY (name, BIC, codes) is supplied per locale
# (see bank_gen/locales/*): each locale maps preset_id -> one of its own banks.
from .locales import BankPresetSpec

BANK_PRESETS: dict[str, BankPresetSpec] = {
    # Broad retail book: family-heavy, full spread of profiles, average dynamics.
    "retail_mass": BankPresetSpec(
        preset_id="retail_mass",
        distribution={
            "etudiant": 0.10, "jeune_actif": 0.20, "famille": 0.28, "cadre": 0.12,
            "csp_plus": 0.04, "freelance": 0.06, "entrepreneur": 0.02,
            "investisseur": 0.01, "retraite": 0.12, "fragile": 0.05,
        },
        transition_propensity={"naissance": 1.2, "achat": 1.1},
    ),
    # Private bank: wealth, upward mobility, low precarity, older (higher mortality).
    "private": BankPresetSpec(
        preset_id="private",
        distribution={
            "cadre": 0.22, "csp_plus": 0.30, "investisseur": 0.18,
            "entrepreneur": 0.12, "famille": 0.10, "retraite": 0.08,
        },
        transition_propensity={"ascension": 1.5, "enrichissement": 2.0,
                               "perte_emploi": 0.4, "retraite": 1.2, "achat": 1.3},
        mortality_scale=1.3,
    ),
    # Young neobank: students/young actives/freelancers, churn-prone, high dormancy.
    "young_neobank": BankPresetSpec(
        preset_id="young_neobank",
        distribution={
            "etudiant": 0.28, "jeune_actif": 0.42, "freelance": 0.14,
            "fragile": 0.10, "famille": 0.06,
        },
        transition_propensity={"ascension": 1.3, "perte_emploi": 1.2,
                               "naissance": 0.8, "retraite": 0.2},
        dormancy_scale=2.5,
    ),
    # Regional bank: balanced, retiree-leaning, stable.
    "regional": BankPresetSpec(
        preset_id="regional",
        distribution={
            "etudiant": 0.06, "jeune_actif": 0.14, "famille": 0.22, "cadre": 0.12,
            "csp_plus": 0.05, "freelance": 0.06, "entrepreneur": 0.02,
            "investisseur": 0.02, "retraite": 0.26, "fragile": 0.05,
        },
        transition_propensity={"perte_emploi": 0.8, "retraite": 1.2},
        mortality_scale=1.2,
    ),
}

# Yearly inflation rate applied to recurring expenses
INFLATION_BY_YEAR = {2022: 0.052, 2023: 0.049, 2024: 0.020, 2025: 0.018, 2026: 0.020}

# Default volumes
DEFAULT_NUM_CUSTOMERS = 60_000
DEFAULT_TARGET_TRANSACTIONS = 5_000_000

# Write batch size (per chunk flushed to disk)
WRITE_BATCH_SIZE = 100_000

# Family situations
FAMILY_SITUATIONS = ["celibataire", "marie", "pacse", "concubinage", "divorce", "veuf"]

# IBAN BBAN format helpers (5 + 5 + 11 + 2)
IBAN_LENGTH = 27  # FR


def gender_distribution() -> list[tuple[str, float]]:
    return [("F", 0.51), ("M", 0.49)]
