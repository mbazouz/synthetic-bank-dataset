"""France locale pack (EUR, fr_FR). Behaviour-preserving port of the original
hardcoded French data so a ``--country fr`` run reproduces the legacy output."""
from __future__ import annotations

import random

from ..banking_utils import generate_iban_fr
from ..config import BANKS, CITIES_FR, FAMILY_SITUATIONS, INFLATION_BY_YEAR
from ..loans import LOAN_TYPES
from ..merchants import LABEL_NOISE, MERCHANTS_STATIC
from ..subscriptions import SUBSCRIPTION_CATALOG
from . import AccountRole, BankPresetSpec, Labels, Locale  # noqa: F401  (BankPresetSpec re-exported)


# Profession buckets per profile (French).
PROFESSIONS = {
    "etudiant":     ("étudiant", "étudiant ingénieur", "doctorant", "alternant"),
    "jeune_actif":  ("développeur", "chef de projet junior", "consultant junior", "data analyst", "commercial"),
    "famille":      ("enseignant", "infirmière", "technicien", "responsable RH", "comptable", "chef d'équipe"),
    "cadre":        ("cadre supérieur", "manager", "directeur de département", "ingénieur senior", "chef de produit"),
    "csp_plus":     ("directeur exécutif", "associé", "médecin spécialiste", "avocat associé", "PDG"),
    "freelance":    ("consultant indépendant", "graphiste freelance", "développeur freelance", "coach", "rédacteur"),
    "entrepreneur": ("fondateur", "dirigeant TPE", "gérant SARL", "chef d'entreprise"),
    "investisseur": ("rentier", "investisseur", "asset manager", "trader"),
    "retraite":     ("retraité", "retraitée ancienne enseignante", "retraité ancien cadre", "retraitée fonction publique"),
    "fragile":      ("sans emploi", "intérimaire", "agent de service", "auxiliaire de vie", "étudiant en alternance"),
}


LABELS = Labels(
    employer_tpl="EMPLOYEUR SAS {n}",
    salary_label_tpl="VIR SALAIRE {payer}",
    pension_payer="CAISSE RETRAITE",
    freelance_merchant="Facture client",
    freelance_label="VIR RECU CLIENT",
    savings_out_merchant="Virement interne épargne",
    savings_out_label_tpl="VIR INTERNE {acct}",
    savings_in_merchant="Virement reçu compte courant",
    savings_in_label="VIR RECU CC",
    landlords=("Bailleur SCI", "Régie immobilière"),
    rent_label="PRELV LOYER",
    reject_merchant_tpl="{bank} - Rejet prélèvement",
    reject_rent_label="FRAIS REJET PRELV LOYER",
    reject_sub_label_tpl="FRAIS REJET PRELV {merchant}",
    reject_loan_label_tpl="FRAIS REJET CREDIT {loan_id}",
    overdraft_merchant_tpl="{bank} - Agios",
    overdraft_label="FRAIS AGIOS DEBITEUR",
    loan_merchant_tpl="{bank} - {title}",
    loan_label_tpl="PRELV CREDIT {kind}",
    atm_merchant="DAB",
    atm_label_tpl="RETRAIT DAB {city}",
    oneshot_merchant_tpl="Événement: {transition}",
    oneshot_label_tpl="DEPENSE {transition}",
    daycare_merchant="Crèche / Assistante maternelle",
)


def _account_identifier(rng: random.Random, bank: dict) -> str:
    return generate_iban_fr(rng, bank["bank_code"])


def _postal_for_region(dept: str, rng: random.Random) -> str:
    # crude CP: dept (2 chars) + 3 digits — mirrors the original customers.py.
    return f"{dept[:2]:>02s}{rng.randint(0, 999):03d}"


LOCALE = Locale(
    code="fr",
    country_code="FR",
    country_name="France",
    currency="EUR",
    faker_locale="fr_FR",
    income_scale=1.0,
    inflation_by_year=INFLATION_BY_YEAR,
    inflation_baseline_year=2022,
    cities=tuple(CITIES_FR),
    family_situations=tuple(FAMILY_SITUATIONS),
    professions=PROFESSIONS,
    gender_dist=(("F", 0.51), ("M", 0.49)),
    banks=tuple(BANKS),
    # BANKS order: Banque Atlas(0), Crédit Synthétique(1), Banque Hexagone(2), Néo Bank IDF(3)
    preset_bank_index={"retail_mass": 0, "private": 1, "regional": 2, "young_neobank": 3},
    account_type_display={
        AccountRole.CURRENT: "compte_courant",
        AccountRole.INVEST: "pea",
        AccountRole.RETIREMENT: "assurance_vie",
        AccountRole.JOINT: "compte_joint",
        AccountRole.BUSINESS: "compte_professionnel",
        AccountRole.HOME_SAVINGS: "pel",
    },
    savings_variants=(("livret_a", 0.7), ("ldds", 0.2), ("lep", 0.1)),
    has_home_savings=True,
    rail_credit="sepa_credit_transfer",
    rail_debit="sepa_direct_debit",
    labels=LABELS,
    merchants=tuple(MERCHANTS_STATIC),
    label_noise=LABEL_NOISE,
    subscription_catalog=tuple(SUBSCRIPTION_CATALOG),
    loan_types=LOAN_TYPES,
    loan_display={
        "credit_immobilier": "Crédit Immobilier",
        "credit_auto": "Crédit Auto",
        "credit_conso": "Crédit Conso",
        "credit_perso": "Crédit Perso",
        "credit_revolving": "Crédit Revolving",
    },
    # FR tokens are already the French display — identity (empty) maps.
    category_display={},
    subcategory_display={},
    profil_display={},
    risk_display={},
    segment_display={},
    family_display={},
    make_account_identifier=_account_identifier,
    phone_format=lambda seq: f"+336{seq:08d}",
    street_format=lambda seq, rng: f"{seq} Rue de la République",
    postal_for_region=_postal_for_region,
)
