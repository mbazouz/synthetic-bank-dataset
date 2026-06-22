"""English display maps for the internal (French) taxonomy tokens.

The engine keeps a single set of canonical tokens for categories, subcategories,
profiles, risk appetite and segments (historically French words) so all the
profile / seasonal / trajectory logic stays locale-independent. These maps
translate those token VALUES to English at OUTPUT time for the en_* locales;
unknown tokens fall through unchanged (``dict.get(token, token)``).

French locales pass empty maps and therefore keep the canonical tokens verbatim.
"""
from __future__ import annotations

CATEGORY_EN = {
    "alimentation": "groceries",
    "restauration": "dining",
    "transport": "transport",
    "shopping": "shopping",
    "voyages": "travel",
    "sante": "health",
    "abonnements": "subscriptions",
    "energie": "utilities",
    "telecom": "telecom",
    "finance": "finance",
    "professionnel": "business",
    "education": "education",
    "logement": "housing",
    "revenus": "income",
    "divers": "other",
}

SUBCATEGORY_EN = {
    # engine-emitted subcategories
    "loyer": "rent",
    "salaire": "salary",
    "pension_retraite": "pension",
    "freelance": "freelance",
    "virement_interne": "internal_transfer",
    "retrait_dab": "atm_withdrawal",
    "agios": "overdraft_fee",
    "frais_bancaires": "bank_fee",
    "credit_immobilier": "mortgage",
    "credit_auto": "auto_loan",
    "credit_conso": "consumer_loan",
    # one-shot life-event transitions (used as subcategory on event rows)
    "entree_vie_active": "first_job",
    "ascension_cadre": "promotion",
    "ascension_csp": "promotion",
    "enrichissement": "windfall",
    "developpement_activite": "business_growth",
    "perte_emploi": "job_loss",
    "echec_entreprise": "business_failure",
    "retour_emploi": "reemployment",
    "naissance_dip": "childbirth",
    "naissance_recovery": "childbirth",
    "mariage": "wedding",
    "divorce": "divorce",
    "achat_immobilier": "home_purchase",
    "achat_voiture": "car_purchase",
    "retraite": "retirement",
    "deces": "deceased",
    "dormance": "dormant",
}

PROFIL_EN = {
    "etudiant": "student",
    "jeune_actif": "young_professional",
    "famille": "family",
    "cadre": "manager",
    "csp_plus": "high_earner",
    "freelance": "freelancer",
    "entrepreneur": "entrepreneur",
    "investisseur": "investor",
    "retraite": "retiree",
    "fragile": "vulnerable",
}

RISK_EN = {
    "prudent": "conservative",
    "modere": "moderate",
    "dynamique": "dynamic",
    "offensif": "aggressive",
}

SEGMENT_EN = {
    "JEUNE": "YOUTH",
    "FRAGILE": "VULNERABLE",
}

# Canonical family-situation tokens (French) -> English; the civil-union term
# differs between the US and the UK, so each locale picks its own.
FAMILY_US = {
    "celibataire": "single",
    "marie": "married",
    "pacse": "domestic_partnership",
    "concubinage": "cohabiting",
    "divorce": "divorced",
    "veuf": "widowed",
}

FAMILY_UK = dict(FAMILY_US, pacse="civil_partnership")
