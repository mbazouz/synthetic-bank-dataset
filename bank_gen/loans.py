"""Loans: mortgage, car loan, consumer credit, personal loan."""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from datetime import date, timedelta

import numpy as np

from .accounts import Account
from .customers import Customer
from .locales import AccountRole, get_locale
from .profiles import PROFILES


@dataclass
class Loan:
    loan_id: str
    customer_id: str
    account_id: str
    type_credit: str
    montant_emprunte: float
    capital_restant: float
    taux_annuel: float
    duree_mois: int
    mensualite: float
    date_debut: date
    date_fin: date
    jour_prelevement: int
    statut: str

    def to_row(self) -> dict:
        return {
            "loan_id": self.loan_id,
            "customer_id": self.customer_id,
            "account_id": self.account_id,
            "loan_type": self.type_credit,
            "principal": self.montant_emprunte,
            "outstanding_balance": self.capital_restant,
            "annual_rate": self.taux_annuel,
            "term_months": self.duree_mois,
            "monthly_payment": self.mensualite,
            "start_date": self.date_debut.isoformat(),
            "end_date": self.date_fin.isoformat(),
            "payment_day": self.jour_prelevement,
            "status": self.statut,
        }


LOAN_TYPES = {
    "credit_immobilier": {"amount_mu": 180_000, "amount_sigma": 80_000, "term_months": [180, 240, 300], "rate": (0.018, 0.045)},
    "credit_auto":       {"amount_mu": 18_000,  "amount_sigma":  9_000, "term_months": [36, 48, 60, 72], "rate": (0.025, 0.065)},
    "credit_conso":      {"amount_mu":  6_500,  "amount_sigma":  3_500, "term_months": [24, 36, 48],     "rate": (0.040, 0.105)},
    "credit_perso":      {"amount_mu": 12_000,  "amount_sigma":  6_000, "term_months": [24, 36, 60],     "rate": (0.045, 0.085)},
    "credit_revolving":  {"amount_mu":  3_500,  "amount_sigma":  2_000, "term_months": [12, 24, 36],     "rate": (0.150, 0.210)},
}


def _profile_loan_mix(profile_name: str, rng: random.Random) -> list[str]:
    if profile_name == "famille":
        return rng.choices(
            [["credit_immobilier"], ["credit_immobilier", "credit_auto"], ["credit_auto"], ["credit_conso"]],
            weights=[0.40, 0.30, 0.15, 0.15],
        )[0]
    if profile_name == "cadre":
        return rng.choices(
            [["credit_immobilier"], ["credit_immobilier", "credit_auto"], ["credit_auto"], []],
            weights=[0.40, 0.25, 0.20, 0.15],
        )[0]
    if profile_name == "csp_plus":
        return rng.choices([["credit_immobilier"], ["credit_immobilier", "credit_auto"], []],
                           weights=[0.55, 0.30, 0.15])[0]
    if profile_name == "jeune_actif":
        return rng.choices([["credit_auto"], ["credit_conso"], ["credit_perso"], []],
                           weights=[0.30, 0.30, 0.15, 0.25])[0]
    if profile_name == "entrepreneur":
        return rng.choices([["credit_immobilier"], ["credit_auto"], ["credit_perso"], []],
                           weights=[0.30, 0.25, 0.20, 0.25])[0]
    if profile_name == "investisseur":
        # Investor: leveraged real estate
        return rng.choices([["credit_immobilier"], ["credit_immobilier", "credit_immobilier"], []],
                           weights=[0.55, 0.25, 0.20])[0]
    if profile_name == "fragile":
        return rng.choices([["credit_conso"], ["credit_revolving"], ["credit_conso", "credit_revolving"], []],
                           weights=[0.35, 0.25, 0.10, 0.30])[0]
    if profile_name == "freelance":
        return rng.choices([["credit_auto"], ["credit_immobilier"], ["credit_perso"], []],
                           weights=[0.25, 0.25, 0.15, 0.35])[0]
    if profile_name == "retraite":
        return rng.choices([["credit_immobilier"], ["credit_auto"], []], weights=[0.10, 0.10, 0.80])[0]
    return rng.choices([["credit_conso"], []], weights=[0.4, 0.6])[0]


def _monthly_payment(principal: float, annual_rate: float, term_months: int) -> float:
    r = annual_rate / 12
    if r == 0:
        return principal / term_months
    return principal * r / (1 - (1 + r) ** -term_months)


def _make_loan(
    loan_id: str, customer: Customer, main_acc: Account, t: str, start: date,
    horizon_start: date, horizon_end: date, rng: random.Random, np_rng: np.random.Generator,
    loan_types: dict,
) -> Loan:
    cfg = loan_types[t]
    mu, sigma = cfg["amount_mu"], cfg["amount_sigma"]
    amount = float(np.clip(np_rng.normal(mu, sigma), mu * 0.4, mu * 2.5))
    if t == "credit_immobilier":
        amount = float(np.clip(amount * (customer.revenu_mensuel / 3000) ** 0.6, 60_000, 900_000))
    elif t == "credit_auto":
        amount = float(np.clip(amount, 4_000, 60_000))
    amount = round(amount, 2)
    term = rng.choice(cfg["term_months"])
    rate = round(rng.uniform(*cfg["rate"]), 4)
    payment = round(_monthly_payment(amount, rate, term), 2)
    end = start + timedelta(days=int(term * 30.4))
    elapsed_months = min(term, max(0, int((horizon_end - start).days / 30.4)))
    r = rate / 12
    if r == 0:
        remaining = amount * (1 - elapsed_months / term)
    else:
        remaining = amount * ((1 + r) ** term - (1 + r) ** elapsed_months) / ((1 + r) ** term - 1)
    remaining = max(0.0, round(remaining, 2))
    statut = "closed" if end < horizon_start else ("active" if remaining > 0 else "closed")
    return Loan(
        loan_id=loan_id, customer_id=customer.customer_id, account_id=main_acc.account_id,
        type_credit=t, montant_emprunte=amount, capital_restant=remaining, taux_annuel=rate,
        duree_mois=term, mensualite=payment, date_debut=start, date_fin=end,
        jour_prelevement=rng.randint(1, 10), statut=statut,
    )


def generate_loans(
    customers: list[Customer],
    accounts_by_customer: dict[str, list[Account]],
    seed: int,
    horizon_start: date,
    horizon_end: date,
    trajectories: dict | None = None,
) -> list[Loan]:
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed + 1)
    trajectories = trajectories or {}
    loans: list[Loan] = []
    next_id = 1

    for customer in customers:
        accs = accounts_by_customer.get(customer.customer_id, [])
        if not accs:
            continue
        profile = PROFILES[customer.profil]
        loan_types = get_locale(customer.locale_code).loan_types
        main_acc = next((a for a in accs if a.role == AccountRole.CURRENT), accs[0])

        # 1) Structural loans originated AT the trajectory event date (home/car purchase).
        structural_types: set[str] = set()
        traj = trajectories.get(customer.customer_id)
        if traj:
            for ph in traj.phases:
                if ph.new_loan and ph.new_loan in loan_types:
                    loans.append(_make_loan(f"L{next_id:07d}", customer, main_acc, ph.new_loan,
                                            ph.start, horizon_start, horizon_end, rng, np_rng, loan_types))
                    next_id += 1
                    structural_types.add(ph.new_loan)

        # 2) Profile-based loans (existing behaviour), skipping types already originated
        #    structurally so a customer never carries two of the same credit.
        if rng.random() <= profile.loan_propensity:
            min_start = max(customer.date_entree_banque, horizon_start - timedelta(days=365 * 8))
            span_days = (horizon_end - min_start).days
            for t in _profile_loan_mix(customer.profil, rng):
                if t not in loan_types or t in structural_types or span_days <= 0:
                    continue
                start = min_start + timedelta(days=rng.randint(0, span_days))
                loans.append(_make_loan(f"L{next_id:07d}", customer, main_acc, t, start,
                                        horizon_start, horizon_end, rng, np_rng, loan_types))
                next_id += 1
    return loans
