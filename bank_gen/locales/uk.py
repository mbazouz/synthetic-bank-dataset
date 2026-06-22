"""United Kingdom locale pack (GBP, en_GB)."""
from __future__ import annotations

import random
import string

from ..banking_utils import generate_iban_gb
from . import AccountRole, Labels, Locale
from .en_display import (
    CATEGORY_EN,
    FAMILY_UK,
    PROFIL_EN,
    RISK_EN,
    SEGMENT_EN,
    SUBCATEGORY_EN,
)


# ---------------------------------------------------------------------------
# Geography
# ---------------------------------------------------------------------------
CITIES = (
    ("London", 9000000, "SW"), ("Birmingham", 1100000, "B"),
    ("Leeds", 790000, "LS"), ("Glasgow", 630000, "G"),
    ("Sheffield", 580000, "S"), ("Manchester", 550000, "M"),
    ("Edinburgh", 530000, "EH"), ("Liverpool", 500000, "L"),
    ("Bristol", 470000, "BS"), ("Cardiff", 360000, "CF"),
    ("Leicester", 360000, "LE"), ("Coventry", 370000, "CV"),
    ("Belfast", 340000, "BT"), ("Nottingham", 330000, "NG"),
    ("Newcastle", 300000, "NE"), ("Brighton", 290000, "BN"),
    ("Plymouth", 260000, "PL"), ("Southampton", 250000, "SO"),
    ("Reading", 230000, "RG"), ("Derby", 260000, "DE"),
    ("Wolverhampton", 260000, "WV"), ("York", 210000, "YO"),
    ("Aberdeen", 200000, "AB"), ("Portsmouth", 240000, "PO"),
    ("Norwich", 200000, "NR"), ("Oxford", 160000, "OX"),
    ("Cambridge", 150000, "CB"), ("Exeter", 130000, "EX"),
    ("Bath", 90000, "BA"), ("Ipswich", 140000, "IP"),
)

FAMILY_SITUATIONS = ("single", "married", "civil_partnership", "cohabiting", "divorced", "widowed")

PROFESSIONS = {
    "etudiant":     ("student", "postgraduate student", "PhD researcher", "apprentice"),
    "jeune_actif":  ("software developer", "junior consultant", "data analyst", "sales executive", "project officer"),
    "famille":      ("teacher", "nurse", "technician", "HR officer", "accountant", "team leader"),
    "cadre":        ("senior manager", "director", "head of department", "senior engineer", "product manager"),
    "csp_plus":     ("managing director", "partner", "consultant surgeon", "solicitor", "chief executive"),
    "freelance":    ("independent consultant", "freelance designer", "freelance developer", "coach", "copywriter"),
    "entrepreneur": ("founder", "small business owner", "company director", "business owner"),
    "investisseur": ("investor", "asset manager", "trader", "fund manager"),
    "retraite":     ("pensioner", "retired teacher", "retired director", "retired civil servant"),
    "fragile":      ("unemployed", "agency worker", "support worker", "carer", "part-time worker"),
}

_STREETS = ("High St", "Station Rd", "Church Ln", "Victoria Rd", "Mill Ln", "Kings Rd",
            "Queens Rd", "Park Rd", "Manor Way", "The Green", "London Rd", "Main St")

INFLATION_BY_YEAR = {2022: 0.079, 2023: 0.067, 2024: 0.025, 2025: 0.025, 2026: 0.022}


# ---------------------------------------------------------------------------
# Banks (bank_code = 4-letter code used in the GB IBAN)
# ---------------------------------------------------------------------------
BANKS = (
    {"name": "Britannia Bank",      "bic": "BRITGB2L", "bank_code": "BRIT"},
    {"name": "Sterling Private Bank", "bic": "STERGB2L", "bank_code": "STER"},
    {"name": "Pennine Regional Bank", "bic": "PENNGB2L", "bank_code": "PENN"},
    {"name": "Monza Neobank",       "bic": "MONZGB2L", "bank_code": "MONZ"},
)


# ---------------------------------------------------------------------------
# Statement labels
# ---------------------------------------------------------------------------
LABELS = Labels(
    employer_tpl="EMPLOYER LTD {n}",
    salary_label_tpl="BACS SALARY {payer}",
    pension_payer="DWP PENSION",
    freelance_merchant="Client Invoice",
    freelance_label="FPS CREDIT INVOICE",
    savings_out_merchant="Transfer to Savings",
    savings_out_label_tpl="TFR TO {acct}",
    savings_in_merchant="Transfer from Current",
    savings_in_label="TFR FROM CURRENT",
    landlords=("Letting Agent Ltd", "Property Management"),
    rent_label="DD RENT",
    reject_merchant_tpl="{bank} - Returned DD",
    reject_rent_label="UNPAID DD RENT",
    reject_sub_label_tpl="UNPAID DD {merchant}",
    reject_loan_label_tpl="UNPAID DD LOAN {loan_id}",
    overdraft_merchant_tpl="{bank} - Overdraft Fee",
    overdraft_label="OVERDRAFT INTEREST",
    loan_merchant_tpl="{bank} - {title}",
    loan_label_tpl="DD LOAN {kind}",
    atm_merchant="CASH MACHINE",
    atm_label_tpl="CASH WITHDRAWAL {city}",
    oneshot_merchant_tpl="Life Event: {transition}",
    oneshot_label_tpl="PURCHASE {transition}",
    daycare_merchant="Nursery",
)


# ---------------------------------------------------------------------------
# Merchant catalogue (GBP). Reuses the shared category tokens.
# ---------------------------------------------------------------------------
MERCHANTS = (
    # Groceries
    ("Tesco",            "5411", "alimentation", "supermarket", 58, 30, "both",     1.0),
    ("Sainsbury's",      "5411", "alimentation", "supermarket", 55, 28, "both",     0.9),
    ("Asda",             "5411", "alimentation", "supermarket", 52, 27, "in_store", 0.9),
    ("Morrisons",        "5411", "alimentation", "supermarket", 50, 26, "in_store", 0.7),
    ("Aldi",             "5411", "alimentation", "supermarket", 38, 18, "in_store", 0.8),
    ("Lidl",             "5411", "alimentation", "supermarket", 36, 17, "in_store", 0.7),
    ("Co-op",            "5411", "alimentation", "convenience", 16, 9,  "in_store", 0.7),
    ("Waitrose",         "5411", "alimentation", "supermarket", 60, 28, "both",     0.5),
    ("M&S Food",         "5411", "alimentation", "supermarket", 28, 14, "in_store", 0.6),
    ("Greggs",           "5462", "alimentation", "bakery",      5,  2,  "in_store", 0.7),
    # Dining
    ("McDonald's",       "5814", "restauration", "fast_food",   8,  4,  "both",     1.0),
    ("Pret A Manger",    "5814", "restauration", "coffee",      7,  3,  "in_store", 0.7),
    ("Costa Coffee",     "5814", "restauration", "coffee",      5,  2,  "both",     0.8),
    ("Nando's",          "5812", "restauration", "restaurant",  22, 9,  "in_store", 0.6),
    ("Wagamama",         "5812", "restauration", "restaurant",  28, 11, "in_store", 0.4),
    ("Local Pub",        "5812", "restauration", "restaurant",  26, 12, "in_store", 0.6),
    ("Deliveroo",        "5812", "restauration", "delivery",    24, 11, "online",   0.8),
    ("Just Eat",         "5812", "restauration", "delivery",    23, 10, "online",   0.7),
    ("Uber Eats",        "5812", "restauration", "delivery",    25, 11, "online",   0.5),
    # Transport
    ("Shell",            "5541", "transport", "fuel",           65, 20, "in_store", 0.9),
    ("BP",               "5541", "transport", "fuel",           63, 19, "in_store", 0.8),
    ("Esso",             "5541", "transport", "fuel",           62, 19, "in_store", 0.6),
    ("Tesco Petrol",     "5541", "transport", "fuel",           60, 18, "in_store", 0.6),
    ("Uber",             "4121", "transport", "rideshare",      14, 7,  "online",   0.7),
    ("Bolt",             "4121", "transport", "rideshare",      12, 6,  "online",   0.4),
    ("TfL",              "4111", "transport", "transit",        2.8, 0.6, "online",  0.8),
    ("Trainline",        "4112", "transport", "rail",           42, 24, "online",   0.5),
    ("NCP Parking",      "7523", "transport", "parking",        9,  5,  "both",     0.4),
    ("Dart Charge",      "4784", "transport", "tolls",          2.5, 0.0, "online",  0.3),
    # Utilities
    ("British Gas",      "4900", "energie", "gas",              90, 40, "online",   1.0),
    ("EDF Energy",       "4900", "energie", "electricity",      85, 38, "online",   0.7),
    ("OVO Energy",       "4900", "energie", "electricity",      82, 36, "online",   0.5),
    ("Thames Water",     "4900", "energie", "water",            42, 18, "online",   0.6),
    # Telecom
    ("EE",               "4814", "telecom", "mobile",           28, 6,  "online",   0.9),
    ("O2",               "4814", "telecom", "mobile",           25, 5,  "online",   0.8),
    ("Vodafone",         "4814", "telecom", "mobile",           24, 5,  "online",   0.7),
    ("BT",               "4899", "telecom", "internet_fixe",    40, 8,  "online",   0.7),
    ("Sky",              "4899", "telecom", "internet_fixe",    46, 9,  "online",   0.6),
    # Subscriptions
    ("Netflix",          "4899", "abonnements", "streaming_video",  10.99, 1, "online", 1.0),
    ("Spotify",          "4899", "abonnements", "streaming_music",  11.99, 0, "online", 0.9),
    ("Disney+",          "4899", "abonnements", "streaming_video",   7.99, 0, "online", 0.6),
    ("Amazon Prime",     "4899", "abonnements", "streaming_video",   8.99, 0, "online", 0.7),
    ("NOW TV",           "4899", "abonnements", "streaming_video",   9.99, 0, "online", 0.4),
    ("Apple iCloud+",    "4899", "abonnements", "cloud",             2.99, 0, "online", 0.6),
    ("PureGym",          "7997", "abonnements", "gym",             24.99, 2, "in_store", 0.5),
    ("Xbox Game Pass",   "4899", "abonnements", "gaming",          12.99, 0, "online", 0.3),
    ("The Times",        "5994", "abonnements", "news",            26.0, 1, "online", 0.3),
    # Shopping
    ("Amazon",           "5942", "shopping", "ecommerce",        36, 26, "online",  1.0),
    ("Argos",            "5942", "shopping", "ecommerce",        45, 28, "both",    0.6),
    ("Currys",           "5722", "shopping", "electronics",      95, 60, "both",    0.5),
    ("John Lewis",       "5651", "shopping", "department",       75, 45, "both",    0.5),
    ("IKEA",             "5712", "shopping", "home_decor",       95, 65, "both",    0.4),
    ("Next",             "5651", "shopping", "clothing",         55, 30, "both",    0.5),
    ("Primark",          "5651", "shopping", "clothing",         32, 16, "in_store", 0.6),
    ("ASOS",             "5651", "shopping", "clothing",         48, 26, "online",  0.5),
    ("Screwfix",         "5211", "shopping", "home_improvement", 42, 28, "both",    0.5),
    ("eBay",             "5942", "shopping", "ecommerce",        38, 26, "online",  0.4),
    # Health
    ("Boots",            "5912", "sante", "pharmacy",            16, 10, "in_store", 0.9),
    ("Superdrug",        "5912", "sante", "pharmacy",            14, 9,  "in_store", 0.6),
    ("NHS Prescription", "5912", "sante", "pharmacy",            9.65, 0, "in_store", 0.7),
    ("Specsavers",       "8043", "sante", "optical",             120, 70, "in_store", 0.3),
    ("Private GP",       "8011", "sante", "doctor",              60, 25, "in_store", 0.3),
    # Travel
    ("Airbnb",           "7011", "voyages", "airbnb",            150, 95, "online",  0.5),
    ("Premier Inn",      "7011", "voyages", "hotel",             95, 45, "online",   0.5),
    ("Booking.com",      "7011", "voyages", "hotel",             130, 80, "online",  0.6),
    ("British Airways",  "4511", "voyages", "flight",            220, 140, "online",  0.4),
    ("easyJet",          "4511", "voyages", "flight",            85, 55, "online",    0.5),
    ("Vue Cinema",       "7832", "voyages", "cinema",            11, 4,  "in_store",  0.5),
    # Education / pro / finance
    ("Open University",  "8220", "education", "tuition",         280, 90, "online",  0.2),
    ("Udemy",            "8299", "education", "online_course",   15, 8,  "online",   0.3),
    ("Adobe",            "5734", "professionnel", "software",    51.99, 0, "online",  0.3),
    ("HMRC",             "9311", "professionnel", "taxes",       420, 230, "online",  0.5),
    ("Hargreaves Lansdown", "6211", "finance", "investment",     250, 150, "online",  0.3),
)

LABEL_NOISE = {
    "Tesco":     ["TESCO STORES", "TESCO", "TESCO EXPRESS", "TESCO PETROL"],
    "Sainsbury's": ["SAINSBURYS", "SAINSBURY'S", "SAINSBURYS S/MKT"],
    "Amazon":    ["AMZNMktplace", "AMAZON.CO.UK", "AMZN MKTP UK", "AMAZON PRIME"],
    "Costa Coffee": ["COSTA COFFEE", "COSTA", "COSTA LTD"],
    "Uber":      ["UBER TRIP", "UBER  *TRIP", "UBER BV"],
    "Netflix":   ["NETFLIX.COM", "NETFLIX", "NETFLIX.COM AMSTERDAM"],
    "Greggs":    ["GREGGS", "GREGGS PLC", "GREGGS THE BAKERS"],
    "TfL":       ["TFL TRAVEL CH", "TFL.GOV.UK/CP", "TFL TRAVEL"],
}

LOAN_TYPES = {
    "credit_immobilier": {"amount_mu": 260_000, "amount_sigma": 110_000, "term_months": [180, 240, 300, 360], "rate": (0.040, 0.062)},
    "credit_auto":       {"amount_mu": 18_000,  "amount_sigma": 9_000,   "term_months": [36, 48, 60],     "rate": (0.060, 0.115)},
    "credit_conso":      {"amount_mu": 8_000,   "amount_sigma": 4_000,   "term_months": [24, 36, 48],     "rate": (0.065, 0.140)},
    "credit_perso":      {"amount_mu": 12_000,  "amount_sigma": 6_000,   "term_months": [24, 36, 60],     "rate": (0.060, 0.110)},
    "credit_revolving":  {"amount_mu": 4_000,   "amount_sigma": 2_200,   "term_months": [12, 24, 36],     "rate": (0.190, 0.290)},
}

LOAN_DISPLAY = {
    "credit_immobilier": "Mortgage",
    "credit_auto": "Car Finance",
    "credit_conso": "Personal Loan",
    "credit_perso": "Personal Loan",
    "credit_revolving": "Overdraft Facility",
}

SUBSCRIPTION_CATALOG = (
    ("EE",             "telecom", "mobile",          28.0, 6.0, 1, {"all": 0.9}),
    ("O2",             "telecom", "mobile",          25.0, 5.0, 1, {"all": 0.6}),
    ("Vodafone",       "telecom", "mobile",          24.0, 5.0, 1, {"all": 0.4}),
    ("BT",             "telecom", "internet_fixe",   40.0, 8.0, 1, {"all": 0.5, "famille": 0.85, "csp_plus": 0.85, "cadre": 0.8}),
    ("Sky",            "telecom", "internet_fixe",   46.0, 9.0, 1, {"all": 0.4, "famille": 0.55}),
    ("Netflix",        "abonnements", "streaming_video",  10.99, 1.0, 1, {"all": 0.55, "etudiant": 0.7, "famille": 0.8}),
    ("Spotify",        "abonnements", "streaming_music",  11.99, 0.0, 1, {"all": 0.45, "etudiant": 0.75, "jeune_actif": 0.75}),
    ("Disney+",        "abonnements", "streaming_video",   7.99, 0.0, 1, {"all": 0.2, "famille": 0.45}),
    ("Amazon Prime",   "abonnements", "streaming_video",   8.99, 0.0, 1, {"all": 0.4}),
    ("NOW TV",         "abonnements", "streaming_video",   9.99, 0.0, 1, {"all": 0.15}),
    ("Apple iCloud+",  "abonnements", "cloud",             2.99, 0.0, 1, {"all": 0.25}),
    ("The Times",      "abonnements", "news",             26.0, 1.0, 1, {"csp_plus": 0.35, "cadre": 0.25, "retraite": 0.15, "all": 0.05}),
    ("PureGym",        "abonnements", "gym",             24.99, 2.0, 1, {"jeune_actif": 0.3, "cadre": 0.2, "all": 0.1}),
    ("Xbox Game Pass", "abonnements", "gaming",          12.99, 0.0, 1, {"etudiant": 0.2, "jeune_actif": 0.15, "all": 0.05}),
    ("British Gas",    "energie", "gas",                 90.0, 40.0, 1, {"all": 0.95}),
    ("EDF Energy",     "energie", "electricity",         85.0, 38.0, 1, {"all": 0.6, "famille": 0.7}),
    ("Thames Water",   "energie", "water",               42.0, 18.0, 3, {"all": 0.55}),
    ("Aviva Home",     "logement", "home_insurance",     18.0, 6.0, 1, {"all": 0.6, "famille": 0.95}),
    ("Admiral Car",    "transport", "car_insurance",     45.0, 16.0, 1, {"all": 0.4, "famille": 0.85, "cadre": 0.7}),
    ("Bupa",           "sante", "health_insurance",      55.0, 20.0, 1, {"csp_plus": 0.5, "cadre": 0.35, "all": 0.1}),
    ("Adobe",          "professionnel", "software",      51.99, 0.0, 1, {"freelance": 0.5, "entrepreneur": 0.4, "all": 0.05}),
    ("Google Workspace","professionnel", "software",     10.0, 0.0, 1, {"freelance": 0.4, "entrepreneur": 0.55, "all": 0.05}),
)


def _account_identifier(rng: random.Random, bank: dict) -> str:
    return generate_iban_gb(rng, bank.get("bank_code", "GBXX"))


def _street(seq: int, rng: random.Random) -> str:
    return f"{1 + seq % 200} {rng.choice(_STREETS)}"


def _postal(region: str, rng: random.Random) -> str:
    a, b = rng.choice(string.ascii_uppercase), rng.choice(string.ascii_uppercase)
    return f"{region}{rng.randint(1, 20)} {rng.randint(1, 9)}{a}{b}"


LOCALE = Locale(
    code="uk",
    country_code="GB",
    country_name="United Kingdom",
    currency="GBP",
    faker_locale="en_GB",
    income_scale=0.95,
    inflation_by_year=INFLATION_BY_YEAR,
    inflation_baseline_year=2022,
    cities=CITIES,
    family_situations=FAMILY_SITUATIONS,
    professions=PROFESSIONS,
    gender_dist=(("F", 0.51), ("M", 0.49)),
    banks=BANKS,
    preset_bank_index={"retail_mass": 0, "private": 1, "regional": 2, "young_neobank": 3},
    account_type_display={
        AccountRole.CURRENT: "current_account",
        AccountRole.INVEST: "stocks_isa",
        AccountRole.RETIREMENT: "sipp",
        AccountRole.JOINT: "joint_current",
        AccountRole.BUSINESS: "business_current",
        AccountRole.HOME_SAVINGS: "cash_isa",
    },
    savings_variants=(("easy_access_saver", 0.6), ("cash_isa", 0.3), ("fixed_saver", 0.1)),
    has_home_savings=False,
    rail_credit="faster_payment",
    rail_debit="bacs_direct_debit",
    labels=LABELS,
    merchants=MERCHANTS,
    label_noise=LABEL_NOISE,
    subscription_catalog=SUBSCRIPTION_CATALOG,
    loan_types=LOAN_TYPES,
    loan_display=LOAN_DISPLAY,
    category_display=CATEGORY_EN,
    subcategory_display=SUBCATEGORY_EN,
    profil_display=PROFIL_EN,
    risk_display=RISK_EN,
    segment_display=SEGMENT_EN,
    family_display=FAMILY_UK,
    make_account_identifier=_account_identifier,
    phone_format=lambda seq: f"+447700900{seq % 1000:03d}",
    street_format=_street,
    postal_for_region=_postal,
)
