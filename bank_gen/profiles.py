"""Profile definitions: income, activity, account mix, risk appetite, etc.

A Profile is a behavioural archetype. Concrete customer parameters are sampled
*from* the profile (e.g. monthly income ~ N(mean, std)) so that two customers
of the same profile do not look identical.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProfileSpec:
    name: str
    age_range: tuple[int, int]
    income_mean: float
    income_std: float
    # share of income spent on rent (mean)
    rent_ratio: float
    # share of income transferred to savings each month
    savings_rate: float
    # transactions per active month (mean) on the main account
    monthly_tx_mean: float
    monthly_tx_std: float
    # likelihood (0..1) that the customer has each kind of account
    has_savings: float = 0.7
    has_pea: float = 0.0
    has_assurance_vie: float = 0.0
    has_pro_account: float = 0.0
    has_joint_account: float = 0.0
    # behaviour
    overdraft_propensity: float = 0.05  # probability of going overdrawn in a given month
    risk_appetite: str = "modere"  # prudent | modere | dynamique | offensif
    # subscription density (avg number of recurring subscriptions)
    subscriptions_mean: float = 3
    # likelihood of taking on a loan over the period
    loan_propensity: float = 0.15
    # typical patrimony multiple of monthly income
    wealth_multiple: tuple[float, float] = (0.5, 4.0)
    # discretionary categories the profile leans towards
    leisure_bias: dict[str, float] = field(default_factory=dict)


PROFILES: dict[str, ProfileSpec] = {
    "etudiant": ProfileSpec(
        name="etudiant",
        age_range=(18, 25),
        income_mean=720,
        income_std=180,
        rent_ratio=0.55,
        savings_rate=0.02,
        monthly_tx_mean=55,
        monthly_tx_std=15,
        has_savings=0.55,
        has_pea=0.02,
        overdraft_propensity=0.25,
        risk_appetite="prudent",
        subscriptions_mean=4,
        loan_propensity=0.08,
        wealth_multiple=(0.1, 1.0),
        leisure_bias={"restauration": 1.5, "abonnements": 1.6, "education": 2.0},
    ),
    "jeune_actif": ProfileSpec(
        name="jeune_actif",
        age_range=(24, 34),
        income_mean=2400,
        income_std=600,
        rent_ratio=0.32,
        savings_rate=0.10,
        monthly_tx_mean=85,
        monthly_tx_std=20,
        has_savings=0.85,
        has_pea=0.15,
        has_assurance_vie=0.15,
        overdraft_propensity=0.10,
        risk_appetite="modere",
        subscriptions_mean=6,
        loan_propensity=0.18,
        wealth_multiple=(0.5, 3.0),
        leisure_bias={"restauration": 1.6, "voyages": 1.4, "abonnements": 1.5, "transport": 1.3},
    ),
    "famille": ProfileSpec(
        name="famille",
        age_range=(30, 50),
        income_mean=4200,
        income_std=1100,
        rent_ratio=0.28,
        savings_rate=0.12,
        monthly_tx_mean=95,
        monthly_tx_std=22,
        has_savings=0.95,
        has_pea=0.25,
        has_assurance_vie=0.40,
        has_joint_account=0.80,
        overdraft_propensity=0.07,
        risk_appetite="modere",
        subscriptions_mean=7,
        loan_propensity=0.55,
        wealth_multiple=(2.0, 12.0),
        leisure_bias={"alimentation": 1.6, "famille": 2.5, "education": 1.7, "transport": 1.3},
    ),
    "cadre": ProfileSpec(
        name="cadre",
        age_range=(28, 55),
        income_mean=5200,
        income_std=1400,
        rent_ratio=0.25,
        savings_rate=0.18,
        monthly_tx_mean=90,
        monthly_tx_std=25,
        has_savings=0.95,
        has_pea=0.45,
        has_assurance_vie=0.55,
        has_joint_account=0.45,
        overdraft_propensity=0.04,
        risk_appetite="dynamique",
        subscriptions_mean=8,
        loan_propensity=0.40,
        wealth_multiple=(3.0, 15.0),
        leisure_bias={"restauration": 1.4, "voyages": 1.7, "shopping": 1.3},
    ),
    "csp_plus": ProfileSpec(
        name="csp_plus",
        age_range=(35, 65),
        income_mean=9800,
        income_std=3500,
        rent_ratio=0.18,
        savings_rate=0.28,
        monthly_tx_mean=110,
        monthly_tx_std=30,
        has_savings=0.98,
        has_pea=0.75,
        has_assurance_vie=0.85,
        has_joint_account=0.50,
        overdraft_propensity=0.02,
        risk_appetite="dynamique",
        subscriptions_mean=10,
        loan_propensity=0.30,
        wealth_multiple=(8.0, 40.0),
        leisure_bias={"voyages": 2.2, "shopping": 1.6, "restauration": 1.5, "famille": 1.2},
    ),
    "freelance": ProfileSpec(
        name="freelance",
        age_range=(25, 55),
        income_mean=3800,
        income_std=1800,  # bigger variance: irregular invoices
        rent_ratio=0.30,
        savings_rate=0.12,
        monthly_tx_mean=110,
        monthly_tx_std=35,
        has_savings=0.80,
        has_pea=0.25,
        has_assurance_vie=0.30,
        has_pro_account=0.85,
        overdraft_propensity=0.18,
        risk_appetite="modere",
        subscriptions_mean=9,  # tools + lifestyle
        loan_propensity=0.20,
        wealth_multiple=(1.0, 8.0),
        leisure_bias={"professionnel": 2.0, "restauration": 1.4, "transport": 1.4},
    ),
    "entrepreneur": ProfileSpec(
        name="entrepreneur",
        age_range=(28, 60),
        income_mean=6500,
        income_std=4000,
        rent_ratio=0.22,
        savings_rate=0.15,
        monthly_tx_mean=140,
        monthly_tx_std=40,
        has_savings=0.85,
        has_pea=0.55,
        has_assurance_vie=0.50,
        has_pro_account=0.95,
        has_joint_account=0.30,
        overdraft_propensity=0.15,
        risk_appetite="offensif",
        subscriptions_mean=12,
        loan_propensity=0.45,
        wealth_multiple=(2.0, 30.0),
        leisure_bias={"professionnel": 2.5, "voyages": 1.6, "restauration": 1.6},
    ),
    "investisseur": ProfileSpec(
        name="investisseur",
        age_range=(35, 70),
        income_mean=4500,  # may also have professional income, mainly lives off capital
        income_std=2200,
        rent_ratio=0.15,
        savings_rate=0.35,
        monthly_tx_mean=70,
        monthly_tx_std=18,
        has_savings=0.95,
        has_pea=0.95,
        has_assurance_vie=0.90,
        overdraft_propensity=0.02,
        risk_appetite="offensif",
        subscriptions_mean=7,
        loan_propensity=0.40,
        wealth_multiple=(15.0, 80.0),
        leisure_bias={"voyages": 1.5, "shopping": 1.2, "finance": 1.8},
    ),
    "retraite": ProfileSpec(
        name="retraite",
        age_range=(63, 88),
        income_mean=1900,
        income_std=600,
        rent_ratio=0.20,
        savings_rate=0.10,
        monthly_tx_mean=45,
        monthly_tx_std=12,
        has_savings=0.95,
        has_pea=0.30,
        has_assurance_vie=0.65,
        has_joint_account=0.45,
        overdraft_propensity=0.04,
        risk_appetite="prudent",
        subscriptions_mean=4,
        loan_propensity=0.08,
        wealth_multiple=(5.0, 25.0),
        leisure_bias={"sante": 1.8, "alimentation": 1.3, "famille": 1.4, "voyages": 1.2},
    ),
    "fragile": ProfileSpec(
        name="fragile",
        age_range=(22, 60),
        income_mean=1450,
        income_std=350,
        rent_ratio=0.45,
        savings_rate=0.0,
        monthly_tx_mean=70,
        monthly_tx_std=20,
        has_savings=0.30,
        overdraft_propensity=0.60,
        risk_appetite="prudent",
        subscriptions_mean=5,
        loan_propensity=0.30,  # often consumer credit
        wealth_multiple=(0.0, 1.0),
        leisure_bias={"alimentation": 1.4, "telecom": 1.2},
    ),
}


def profile_for(name: str) -> ProfileSpec:
    return PROFILES[name]
