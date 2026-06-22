"""Subscription generation.

Each subscription has a merchant, an amount, a recurrence (monthly/annual),
a billing day of month and a start/end date. The transaction engine consumes
this table to inject SEPA direct-debit transactions on the right day.
"""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from datetime import date, timedelta

import numpy as np

from .accounts import Account
from .customers import Customer
from .locales import AccountRole, get_locale
from .profiles import PROFILES


# Curated subscription catalogue (merchant_name, label_category, label_sub, amount_mu, amount_sigma, freq_months, popularity_by_profile)
SUBSCRIPTION_CATALOG = [
    # Telecom
    ("Free Mobile",   "telecom", "mobile",          15.99, 0.0,  1, {"all": 0.9}),
    ("Orange",        "telecom", "mobile",          24.99, 4.0,  1, {"all": 0.6}),
    ("Sosh",          "telecom", "mobile",          14.99, 1.0,  1, {"all": 0.3}),
    ("Bouygues Telecom","telecom","mobile",         17.99, 3.0,  1, {"all": 0.3}),
    ("SFR",           "telecom", "mobile",          19.99, 3.0,  1, {"all": 0.3}),
    ("Free",          "telecom", "internet_fixe",   29.99, 0.0,  1, {"all": 0.5, "famille": 0.85, "csp_plus": 0.85, "cadre": 0.8}),
    ("Orange Internet","telecom","internet_fixe",   39.99, 4.0,  1, {"all": 0.4, "famille": 0.5}),
    # Streaming
    ("Netflix",       "abonnements", "streaming_video",  13.49, 1.0, 1, {"all": 0.55, "etudiant": 0.7, "famille": 0.8}),
    ("Spotify",       "abonnements", "streaming_musique",10.99, 0.0, 1, {"all": 0.45, "etudiant": 0.75, "jeune_actif": 0.75}),
    ("Deezer",        "abonnements", "streaming_musique", 9.99, 0.0, 1, {"all": 0.15}),
    ("Disney+",       "abonnements", "streaming_video",  8.99, 0.0, 1, {"all": 0.20, "famille": 0.45}),
    ("Amazon Prime",  "abonnements", "streaming_video",  6.99, 0.0, 1, {"all": 0.35}),
    ("Canal+",        "abonnements", "streaming_video", 24.99, 3.0, 1, {"all": 0.10, "famille": 0.20}),
    ("Apple One",     "abonnements", "streaming_video", 16.99, 2.0, 1, {"all": 0.15, "csp_plus": 0.30}),
    ("YouTube Premium","abonnements","streaming_video", 11.99, 0.0, 1, {"all": 0.15}),
    ("iCloud+",       "abonnements", "cloud",            2.99, 0.0, 1, {"all": 0.25}),
    ("Google One",    "abonnements", "cloud",            1.99, 0.0, 1, {"all": 0.15}),
    # Press
    ("Le Monde",      "abonnements", "presse",          12.90, 1.0, 1, {"csp_plus": 0.35, "cadre": 0.25, "retraite": 0.15, "all": 0.05}),
    ("Mediapart",     "abonnements", "presse",          11.00, 0.0, 1, {"csp_plus": 0.20, "cadre": 0.15, "all": 0.04}),
    # Gym
    ("Basic Fit",     "abonnements", "salle_sport",     24.99, 2.0, 1, {"jeune_actif": 0.30, "cadre": 0.20, "all": 0.10}),
    ("Fitness Park",  "abonnements", "salle_sport",     19.99, 2.0, 1, {"jeune_actif": 0.20, "all": 0.08}),
    # Gaming
    ("PlayStation Plus","abonnements","gaming",         8.99, 0.0, 1, {"etudiant": 0.20, "jeune_actif": 0.15, "all": 0.05}),
    ("Xbox Game Pass","abonnements", "gaming",         12.99, 0.0, 1, {"etudiant": 0.15, "all": 0.05}),
    # Utilities (often direct-debit)
    ("EDF",           "energie",    "electricite",     95.0, 40.0, 1, {"all": 0.95}),
    ("Engie",         "energie",    "gaz",             75.0, 35.0, 1, {"all": 0.45, "famille": 0.70}),
    ("Veolia",        "energie",    "eau",             45.0, 22.0, 3, {"all": 0.55}),
    # Insurance
    ("AXA Habitation","logement",   "assurance_habitation",18.5, 6.0, 1, {"all": 0.60, "famille": 0.95}),
    ("MAIF Auto",     "transport",  "carburant",       35.0, 12.0, 1, {"all": 0.40, "famille": 0.85, "cadre": 0.70}),
    ("Harmonie Mutuelle","sante",   "mutuelle",        58.0, 22.0, 1, {"all": 0.55, "famille": 0.90, "retraite": 0.95}),
    # Pro tools
    ("Adobe Creative Cloud","professionnel","logiciels_pro",59.99, 0.0, 1, {"freelance": 0.50, "entrepreneur": 0.40, "all": 0.05}),
    ("Notion",        "professionnel","logiciels_pro",  9.0,  0.0, 1, {"freelance": 0.30, "entrepreneur": 0.35, "all": 0.05}),
    ("Slack",         "professionnel","logiciels_pro", 12.5,  0.0, 1, {"freelance": 0.25, "entrepreneur": 0.40, "all": 0.04}),
    ("Google Workspace","professionnel","logiciels_pro",9.36, 0.0, 1, {"freelance": 0.40, "entrepreneur": 0.55, "all": 0.05}),
    ("OVHcloud",      "professionnel","logiciels_pro", 18.0,  9.0, 1, {"freelance": 0.30, "entrepreneur": 0.40, "all": 0.03}),
]


@dataclass
class Subscription:
    subscription_id: str
    customer_id: str
    account_id: str
    merchant_name: str
    category: str
    subcategory: str
    amount: float
    frequency_months: int
    billing_day: int
    start_date: date
    end_date: date | None
    statut: str  # active / churned

    def to_row(self) -> dict:
        return {
            "subscription_id": self.subscription_id,
            "customer_id": self.customer_id,
            "account_id": self.account_id,
            "merchant_name": self.merchant_name,
            "category": self.category,
            "subcategory": self.subcategory,
            "amount": self.amount,
            "frequency_months": self.frequency_months,
            "billing_day": self.billing_day,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "status": self.statut,
        }


def _pick_for_profile(profile_name: str, pop: dict[str, float]) -> float:
    return pop.get(profile_name, pop.get("all", 0.0))


def generate_subscriptions(
    customers: list[Customer],
    accounts_by_customer: dict[str, list[Account]],
    seed: int,
    start_date: date,
    end_date: date,
    trajectories: dict | None = None,
) -> list[Subscription]:
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed + 1)
    trajectories = trajectories or {}
    subs: list[Subscription] = []
    next_id = 1

    for customer in customers:
        accs = accounts_by_customer.get(customer.customer_id, [])
        if not accs:
            continue
        loc = get_locale(customer.locale_code)
        catalog = loc.subscription_catalog
        main_acc = next((a for a in accs if a.role == AccountRole.CURRENT), accs[0])
        pro_acc = next((a for a in accs if a.role == AccountRole.BUSINESS), None)
        profile = PROFILES[customer.profil]
        target_n = max(0, int(round(np_rng.normal(profile.subscriptions_mean, 1.5))))

        chosen: set[str] = set()
        attempts = 0
        while len(chosen) < target_n and attempts < target_n * 5 + 10:
            attempts += 1
            cand = rng.choice(catalog)
            name = cand[0]
            if name in chosen:
                continue
            prob = _pick_for_profile(customer.profil, cand[6])
            if rng.random() > prob:
                continue
            chosen.add(name)
            mu, sigma, freq = cand[3], cand[4], cand[5]
            amount = round(float(np.clip(np_rng.normal(mu, sigma or 0.0001), max(1.0, mu * 0.4), mu * 1.8)), 2)
            billing_day = rng.randint(1, 28)
            # Subscription starts somewhere in the period (or before)
            offset_days = rng.randint(-365, (end_date - start_date).days - 60)
            sub_start = start_date + timedelta(days=offset_days)
            # Subscription may churn (15% chance to end before end_date)
            if rng.random() < 0.15:
                sub_end_offset = rng.randint(180, max(181, (end_date - sub_start).days - 30))
                sub_end = sub_start + timedelta(days=sub_end_offset)
                statut = "churned"
            else:
                sub_end = None
                statut = "active"

            is_pro = cand[1] == "professionnel"
            account = pro_acc if (is_pro and pro_acc is not None) else main_acc

            subs.append(Subscription(
                subscription_id=f"S{next_id:08d}",
                customer_id=customer.customer_id,
                account_id=account.account_id,
                merchant_name=name,
                category=cand[1],
                subcategory=cand[2],
                amount=amount,
                frequency_months=freq,
                billing_day=billing_day,
                start_date=sub_start,
                end_date=sub_end,
                statut=statut,
            ))
            next_id += 1

        # Structural subscription: daycare opened at a `naissance` trajectory phase,
        # running ~3 years, so the birth shows up as recurring famille spending.
        traj = trajectories.get(customer.customer_id)
        if traj:
            for ph in traj.phases:
                if ph.new_subscription != "creche":
                    continue
                amount = round(float(np.clip(np_rng.normal(600, 180), 250, 1100)), 2)
                creche_end = min(ph.start + timedelta(days=int(3 * 365)), end_date)
                subs.append(Subscription(
                    subscription_id=f"S{next_id:08d}",
                    customer_id=customer.customer_id,
                    account_id=main_acc.account_id,
                    merchant_name=loc.labels.daycare_merchant,
                    category="famille",
                    subcategory="garde_enfant",
                    amount=amount,
                    frequency_months=1,
                    billing_day=rng.randint(1, 10),
                    start_date=ph.start,
                    end_date=creche_end,
                    statut="active",
                ))
                next_id += 1
    return subs
