"""Locale packs: per-country data and wording for the generator.

A ``Locale`` is a passive data bundle that localizes every value the engine
emits — names, cities, banks, account-type display strings, currency, statement
labels, merchant catalogue, subscriptions and loan products — WITHOUT changing
the internal raw column names or the abstract taxonomy tokens (category /
profile / transition / family-situation tokens stay identical across locales, so
the profile, trajectory and seasonal logic need no per-locale branches).

Supported countries: ``fr`` (France), ``us`` (United States), ``uk`` (United
Kingdom). The special selector ``mix`` assigns a country per customer.

The default country is ``us``.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable


# ---------------------------------------------------------------------------
# Account roles — locale-neutral logical kinds.
#
# The raw ``type_compte`` column holds a LOCALE display string (e.g.
# "compte_courant" / "checking" / "current_account"); the engine and the
# delivery exporter switch on the ROLE instead, so no code string-matches a
# French product name.
# ---------------------------------------------------------------------------
class AccountRole:
    CURRENT = "CURRENT"
    SAVINGS = "SAVINGS"
    HOME_SAVINGS = "HOME_SAVINGS"   # FR PEL; folded into SAVINGS for the contract
    INVEST = "INVEST"               # FR PEA / US brokerage / UK stocks ISA
    RETIREMENT = "RETIREMENT"       # FR assurance-vie / US IRA / UK SIPP
    JOINT = "JOINT"
    BUSINESS = "BUSINESS"

    ALL = (CURRENT, SAVINGS, HOME_SAVINGS, INVEST, RETIREMENT, JOINT, BUSINESS)
    # Roles that receive the automatic month-end savings sweep.
    SWEEP_TARGETS = (SAVINGS, HOME_SAVINGS)


# ---------------------------------------------------------------------------
# Statement-label phrase pack
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Labels:
    """Wording for every statement line the transaction engine emits.

    Templates use ``str.format`` placeholders. Abstract tokens (transition
    names, account roles) are passed through verbatim — only the wrapper
    phrasing is localized.
    """
    # --- salary / income ---
    employer_tpl: str               # "EMPLOYEUR SAS {n}"
    salary_label_tpl: str           # "VIR SALAIRE {payer}"
    pension_payer: str              # "CAISSE RETRAITE"
    freelance_merchant: str         # "Facture client"
    freelance_label: str            # "VIR RECU CLIENT"
    # --- internal savings sweep ---
    savings_out_merchant: str       # "Virement interne épargne"
    savings_out_label_tpl: str      # "VIR INTERNE {acct}"
    savings_in_merchant: str        # "Virement reçu compte courant"
    savings_in_label: str           # "VIR RECU CC"
    # --- rent ---
    landlords: tuple[str, ...]      # ("Bailleur SCI", "Régie immobilière")
    rent_label: str                 # "PRELV LOYER"
    # --- bank fees / rejects (merchant carries the real bank name) ---
    reject_merchant_tpl: str        # "{bank} - Rejet prélèvement"
    reject_rent_label: str          # "FRAIS REJET PRELV LOYER"
    reject_sub_label_tpl: str       # "FRAIS REJET PRELV {merchant}"
    reject_loan_label_tpl: str      # "FRAIS REJET CREDIT {loan_id}"
    overdraft_merchant_tpl: str     # "{bank} - Agios"
    overdraft_label: str            # "FRAIS AGIOS DEBITEUR"
    # --- loans ---
    loan_merchant_tpl: str          # "{bank} - {title}"
    loan_label_tpl: str             # "PRELV CREDIT {kind}"
    # --- cash / ATM ---
    atm_merchant: str               # "DAB"
    atm_label_tpl: str              # "RETRAIT DAB {city}"
    # --- one-shot life events ---
    oneshot_merchant_tpl: str       # "Événement: {transition}"
    oneshot_label_tpl: str          # "DEPENSE {transition}"
    # --- structural subscriptions ---
    daycare_merchant: str           # "Crèche / Assistante maternelle"

    # convenience formatters -------------------------------------------------
    def employer(self, n: int) -> str:
        return self.employer_tpl.format(n=n)

    def salary_label(self, payer: str) -> str:
        return self.salary_label_tpl.format(payer=payer)

    def savings_out_label(self, acct_display: str) -> str:
        return self.savings_out_label_tpl.format(acct=acct_display.upper())

    def reject_merchant(self, bank: str) -> str:
        return self.reject_merchant_tpl.format(bank=bank)

    def reject_sub_label(self, merchant: str) -> str:
        return self.reject_sub_label_tpl.format(merchant=merchant.upper())

    def reject_loan_label(self, loan_id: str) -> str:
        return self.reject_loan_label_tpl.format(loan_id=loan_id)

    def overdraft_merchant(self, bank: str) -> str:
        return self.overdraft_merchant_tpl.format(bank=bank)

    def loan_merchant(self, bank: str, title: str) -> str:
        return self.loan_merchant_tpl.format(bank=bank, title=title)

    def loan_label(self, title: str) -> str:
        return self.loan_label_tpl.format(kind=title.upper())

    def atm_label(self, city: str) -> str:
        return self.atm_label_tpl.format(city=city.upper())

    def oneshot_merchant(self, transition: str) -> str:
        return self.oneshot_merchant_tpl.format(transition=transition)

    def oneshot_label(self, transition: str) -> str:
        return self.oneshot_label_tpl.format(transition=transition.upper())


# ---------------------------------------------------------------------------
# Bank preset archetype — behaviour knobs, decoupled from bank identity.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BankPresetSpec:
    preset_id: str
    distribution: dict[str, float]                       # per-bank profile mix (sums to 1.0)
    transition_propensity: dict[str, float] = field(default_factory=dict)
    mortality_scale: float = 1.0
    dormancy_scale: float = 1.0


# ---------------------------------------------------------------------------
# Locale
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Locale:
    code: str                       # "fr" | "us" | "uk"
    country_code: str               # "FR" | "US" | "GB"
    country_name: str               # "France" | "United States" | "United Kingdom"
    currency: str                   # "EUR" | "USD" | "GBP"
    faker_locale: str               # "fr_FR" | "en_US" | "en_GB"
    income_scale: float             # multiplies the shared (EUR-baseline) profile incomes

    # inflation
    inflation_by_year: dict[int, float]
    inflation_baseline_year: int

    # geography: (city_name, population_weight, region_code)
    cities: tuple[tuple[str, int, str], ...]
    family_situations: tuple[str, ...]
    professions: dict[str, tuple[str, ...]]   # keyed by profile token
    gender_dist: tuple[tuple[str, float], ...]

    # banks + preset→bank binding
    banks: tuple[dict, ...]
    preset_bank_index: dict[str, int]         # preset_id -> index into banks

    # account types
    account_type_display: dict[str, str]      # role -> display string (1:1 roles)
    savings_variants: tuple[tuple[str, float], ...]  # (display, weight) for the SAVINGS role
    has_home_savings: bool

    # payment rails (internal transaction_type values)
    rail_credit: str                # "sepa_credit_transfer" | "ach_credit" | "faster_payment"
    rail_debit: str                 # "sepa_direct_debit" | "ach_debit" | "bacs_direct_debit"

    # catalogues
    labels: Labels
    merchants: tuple[tuple, ...]                # same 8-tuple shape as the old MERCHANTS_STATIC
    label_noise: dict[str, list[str]]
    subscription_catalog: tuple[tuple, ...]    # same shape as the old SUBSCRIPTION_CATALOG
    loan_types: dict[str, dict]                # same shape as the old LOAN_TYPES (native currency)
    loan_display: dict[str, str]               # loan token -> human label ("Crédit Immobilier" / "Mortgage")

    # output display maps (canonical token -> localized value); empty = identity
    category_display: dict[str, str]
    subcategory_display: dict[str, str]
    profil_display: dict[str, str]
    risk_display: dict[str, str]
    segment_display: dict[str, str]
    family_display: dict[str, str]

    # identifiers + PII formatters
    make_account_identifier: Callable[[random.Random, dict], str]
    phone_format: Callable[[int], str]
    street_format: Callable[[int, random.Random], str]
    postal_for_region: Callable[[str, random.Random], str]

    # helpers ---------------------------------------------------------------
    def bank_for_preset(self, preset_id: str, rng: random.Random) -> dict:
        idx = self.preset_bank_index.get(preset_id)
        if idx is None or idx >= len(self.banks):
            return rng.choice(self.banks)
        return self.banks[idx]

    def display_for_role(self, role: str) -> str:
        return self.account_type_display.get(role, role.lower())

    # output-time token translation (identity when the map has no entry) -------
    def tx_category(self, token: str) -> str:
        return self.category_display.get(token, token)

    def tx_subcategory(self, token: str) -> str:
        return self.subcategory_display.get(token, token)

    def cust_profil(self, token: str) -> str:
        return self.profil_display.get(token, token)

    def cust_risk(self, token: str) -> str:
        return self.risk_display.get(token, token)

    def cust_segment(self, token: str) -> str:
        return self.segment_display.get(token, token)

    def cust_family(self, token: str) -> str:
        return self.family_display.get(token, token)


# ---------------------------------------------------------------------------
# Registry + resolution
# ---------------------------------------------------------------------------
MIX_CODES = ("us", "uk", "fr")
MIX_WEIGHTS = (0.45, 0.30, 0.25)
# Per-locale salt so each locale's Faker instance starts from a distinct stream.
LOCALE_SALT = {"us": 0, "uk": 101, "fr": 202}


def get_locale(code: str) -> Locale:
    code = (code or "").lower()
    if code == "fr":
        from . import fr as mod
    elif code == "us":
        from . import us as mod
    elif code == "uk":
        from . import uk as mod
    else:
        raise SystemExit(f"Unknown country '{code}'. Choose one of: fr, us, uk, mix.")
    return mod.LOCALE


def all_locale_codes() -> tuple[str, ...]:
    return ("fr", "us", "uk")
