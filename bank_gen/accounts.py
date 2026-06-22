"""Account generation: one customer => one or several accounts.

Each account carries a locale-neutral ``role`` (CURRENT / SAVINGS / …) used by
the transaction engine and the delivery exporter, plus a locale ``type_compte``
display string (e.g. compte_courant / checking / current_account).
"""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from datetime import date, timedelta

from .customers import Customer
from .locales import AccountRole, Locale, get_locale
from .profiles import PROFILES


@dataclass
class Account:
    account_id: str
    customer_id: str
    iban: str
    bic: str
    bank_name: str
    type_compte: str        # locale display string
    role: str               # AccountRole.* — locale-neutral logical kind
    date_ouverture: date
    solde_initial: float
    solde_actuel: float
    autorisation_decouvert: float
    statut: str

    def to_row(self) -> dict:
        return {
            "account_id": self.account_id,
            "customer_id": self.customer_id,
            "iban": self.iban,
            "bic": self.bic,
            "bank_name": self.bank_name,
            "account_type": self.type_compte,
            "role": self.role,
            "opened_at": self.date_ouverture.isoformat(),
            "initial_balance": self.solde_initial,
            "current_balance": self.solde_actuel,
            "overdraft_limit": self.autorisation_decouvert,
            "status": self.statut,
        }


# Opening-balance range (× monthly revenue) keyed by role.
_OPENING_BALANCE_RANGE = {
    AccountRole.CURRENT:      (0.2, 2.5),
    AccountRole.SAVINGS:      (0.4, 8.0),
    AccountRole.HOME_SAVINGS: (3.0, 25.0),
    AccountRole.INVEST:       (3.0, 40.0),
    AccountRole.RETIREMENT:   (4.0, 50.0),
    AccountRole.JOINT:        (0.5, 3.5),
    AccountRole.BUSINESS:     (0.2, 8.0),
}


def _opening_balance(role: str, customer: Customer, rng: random.Random) -> float:
    lo, hi = _OPENING_BALANCE_RANGE.get(role, (0.0, 0.0))
    if hi <= 0:
        return 0.0
    return round(rng.uniform(lo, hi) * customer.revenu_mensuel, 2)


def _overdraft_for(profile_name: str, role: str, revenue: float) -> float:
    if role != AccountRole.CURRENT:
        return 0.0
    base = {
        "etudiant": 200, "jeune_actif": 600, "famille": 1500, "cadre": 2500,
        "csp_plus": 5000, "freelance": 1500, "entrepreneur": 3500,
        "investisseur": 4000, "retraite": 800, "fragile": 200,
    }.get(profile_name, 1000)
    return round(min(base, revenue * 0.8), 2)


def _pick_savings_variant(locale: Locale, rng: random.Random) -> str:
    variants = locale.savings_variants
    return rng.choices([v[0] for v in variants], weights=[v[1] for v in variants], k=1)[0]


def generate_accounts(customers: list[Customer], seed: int) -> list[Account]:
    rng = random.Random(seed)
    accounts: list[Account] = []
    next_id = 1
    for customer in customers:
        loc = get_locale(customer.locale_code)
        profile = PROFILES[customer.profil]
        bank = loc.bank_for_preset(customer.bank_preset, rng) if customer.bank_preset \
            else rng.choice(loc.banks)

        # Build the (role, display) pairs this customer owns. CURRENT always first.
        owned: list[tuple[str, str]] = [(AccountRole.CURRENT, loc.display_for_role(AccountRole.CURRENT))]
        if rng.random() < profile.has_savings:
            owned.append((AccountRole.SAVINGS, _pick_savings_variant(loc, rng)))
        if rng.random() < profile.has_pea:
            owned.append((AccountRole.INVEST, loc.display_for_role(AccountRole.INVEST)))
        if rng.random() < profile.has_assurance_vie:
            owned.append((AccountRole.RETIREMENT, loc.display_for_role(AccountRole.RETIREMENT)))
        if rng.random() < profile.has_pro_account:
            owned.append((AccountRole.BUSINESS, loc.display_for_role(AccountRole.BUSINESS)))
        if rng.random() < profile.has_joint_account:
            owned.append((AccountRole.JOINT, loc.display_for_role(AccountRole.JOINT)))
        # families and CSP+ may hold a home-savings plan too (FR PEL; locales
        # without one simply skip after the draw, keeping streams aligned).
        if customer.profil in ("famille", "csp_plus", "cadre") and rng.random() < 0.25:
            if loc.has_home_savings:
                owned.append((AccountRole.HOME_SAVINGS, loc.display_for_role(AccountRole.HOME_SAVINGS)))

        for role, display in owned:
            if role == AccountRole.CURRENT:
                opened = customer.date_entree_banque
            else:
                # secondary accounts open 0 - 8 years after the main account
                opened = customer.date_entree_banque + timedelta(days=rng.randint(60, 8 * 365))
                opened = min(opened, date.today() - timedelta(days=1))
            solde_initial = _opening_balance(role, customer, rng)
            accounts.append(Account(
                account_id=f"A{next_id:08d}",
                customer_id=customer.customer_id,
                iban=loc.make_account_identifier(rng, bank),
                bic=bank.get("bic", ""),
                bank_name=bank["name"],
                type_compte=display,
                role=role,
                date_ouverture=opened,
                solde_initial=solde_initial,
                solde_actuel=solde_initial,  # updated by the tx engine
                autorisation_decouvert=_overdraft_for(customer.profil, role, customer.revenu_mensuel),
                statut="active",
            ))
            next_id += 1
    return accounts
