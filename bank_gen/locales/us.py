"""United States locale pack (USD, en_US)."""
from __future__ import annotations

import random

from ..banking_utils import generate_account_number_us
from . import AccountRole, Labels, Locale
from .en_display import (
    CATEGORY_EN,
    FAMILY_US,
    PROFIL_EN,
    RISK_EN,
    SEGMENT_EN,
    SUBCATEGORY_EN,
)


# ---------------------------------------------------------------------------
# Geography
# ---------------------------------------------------------------------------
CITIES = (
    ("New York", 8400000, "100"), ("Los Angeles", 3900000, "900"),
    ("Chicago", 2700000, "606"), ("Houston", 2300000, "770"),
    ("Phoenix", 1600000, "850"), ("Philadelphia", 1580000, "191"),
    ("San Antonio", 1500000, "782"), ("San Diego", 1400000, "921"),
    ("Dallas", 1300000, "752"), ("Austin", 980000, "787"),
    ("San Jose", 1000000, "951"), ("Jacksonville", 950000, "322"),
    ("Columbus", 900000, "432"), ("Charlotte", 880000, "282"),
    ("Indianapolis", 870000, "462"), ("San Francisco", 870000, "941"),
    ("Seattle", 750000, "981"), ("Denver", 710000, "802"),
    ("Boston", 690000, "021"), ("Nashville", 690000, "372"),
    ("Detroit", 670000, "482"), ("Portland", 650000, "972"),
    ("Las Vegas", 640000, "891"), ("Memphis", 630000, "381"),
    ("Atlanta", 500000, "303"), ("Miami", 470000, "331"),
    ("Minneapolis", 430000, "554"), ("Tampa", 400000, "336"),
    ("New Orleans", 390000, "701"), ("Cleveland", 370000, "441"),
    ("Pittsburgh", 300000, "152"), ("St. Louis", 300000, "631"),
    ("Cincinnati", 300000, "452"), ("Kansas City", 510000, "641"),
    ("Sacramento", 520000, "958"), ("Salt Lake City", 200000, "841"),
)

FAMILY_SITUATIONS = ("single", "married", "domestic_partnership", "cohabiting", "divorced", "widowed")

PROFESSIONS = {
    "etudiant":     ("student", "graduate student", "PhD candidate", "intern"),
    "jeune_actif":  ("software engineer", "junior consultant", "data analyst", "sales associate", "project coordinator"),
    "famille":      ("teacher", "registered nurse", "technician", "HR manager", "accountant", "team lead"),
    "cadre":        ("senior manager", "director", "department head", "senior engineer", "product manager"),
    "csp_plus":     ("executive director", "partner", "physician", "attorney", "CEO"),
    "freelance":    ("independent consultant", "freelance designer", "freelance developer", "coach", "copywriter"),
    "entrepreneur": ("founder", "small business owner", "managing member", "business owner"),
    "investisseur": ("investor", "asset manager", "trader", "portfolio manager"),
    "retraite":     ("retiree", "retired teacher", "retired executive", "retired civil servant"),
    "fragile":      ("unemployed", "temp worker", "service worker", "home aide", "part-time worker"),
}

_STREETS = ("Main St", "Oak Ave", "Maple Dr", "Elm St", "Cedar Ln", "Park Ave",
            "Washington Blvd", "Lake Rd", "Hill St", "Sunset Blvd", "Pine St", "2nd Ave")

INFLATION_BY_YEAR = {2022: 0.065, 2023: 0.041, 2024: 0.029, 2025: 0.026, 2026: 0.026}


# ---------------------------------------------------------------------------
# Banks
# ---------------------------------------------------------------------------
BANKS = (
    {"name": "First National Bank", "bic": "", "bank_code": "021000021"},
    {"name": "Summit Private Bank",  "bic": "", "bank_code": "026009593"},
    {"name": "Cardinal Regional Bank", "bic": "", "bank_code": "011401533"},
    {"name": "Vela Neobank",         "bic": "", "bank_code": "031176110"},
)


# ---------------------------------------------------------------------------
# Statement labels
# ---------------------------------------------------------------------------
LABELS = Labels(
    employer_tpl="EMPLOYER LLC {n}",
    salary_label_tpl="DIRECT DEP {payer}",
    pension_payer="SOCIAL SECURITY",
    freelance_merchant="Client Invoice",
    freelance_label="ACH DEPOSIT INVOICE",
    savings_out_merchant="Transfer to Savings",
    savings_out_label_tpl="XFER TO {acct}",
    savings_in_merchant="Transfer from Checking",
    savings_in_label="XFER FROM CHK",
    landlords=("Property Mgmt LLC", "Realty Partners"),
    rent_label="ACH RENT",
    reject_merchant_tpl="{bank} - Returned Item",
    reject_rent_label="NSF FEE RENT",
    reject_sub_label_tpl="NSF FEE {merchant}",
    reject_loan_label_tpl="NSF FEE LOAN {loan_id}",
    overdraft_merchant_tpl="{bank} - Overdraft Fee",
    overdraft_label="OVERDRAFT FEE",
    loan_merchant_tpl="{bank} - {title}",
    loan_label_tpl="LOAN PMT {kind}",
    atm_merchant="ATM",
    atm_label_tpl="ATM WITHDRAWAL {city}",
    oneshot_merchant_tpl="Life Event: {transition}",
    oneshot_label_tpl="PURCHASE {transition}",
    daycare_merchant="Childcare Center",
)


# ---------------------------------------------------------------------------
# Merchant catalogue (USD). Reuses the shared category tokens.
# ---------------------------------------------------------------------------
MERCHANTS = (
    # Groceries
    ("Walmart",          "5411", "alimentation", "supermarket", 72, 38, "both",     1.0),
    ("Kroger",           "5411", "alimentation", "supermarket", 64, 34, "in_store", 0.9),
    ("Costco",           "5411", "alimentation", "supermarket", 140, 70, "in_store", 0.8),
    ("Target",           "5411", "alimentation", "supermarket", 58, 32, "both",     0.9),
    ("Safeway",          "5411", "alimentation", "supermarket", 55, 28, "in_store", 0.7),
    ("Whole Foods",      "5411", "alimentation", "supermarket", 68, 30, "both",     0.6),
    ("Trader Joe's",     "5411", "alimentation", "supermarket", 42, 20, "in_store", 0.7),
    ("Aldi",             "5411", "alimentation", "supermarket", 38, 18, "in_store", 0.6),
    ("7-Eleven",         "5411", "alimentation", "convenience", 14, 8,  "in_store", 0.7),
    ("Local Bakery",     "5462", "alimentation", "bakery",      9,  4,  "in_store", 0.5),
    # Dining
    ("McDonald's",       "5814", "restauration", "fast_food",   11, 5,  "both",     1.0),
    ("Chipotle",         "5814", "restauration", "fast_food",   13, 5,  "both",     0.8),
    ("Starbucks",        "5814", "restauration", "coffee",      7,  3,  "both",     0.9),
    ("Chick-fil-A",      "5814", "restauration", "fast_food",   12, 5,  "both",     0.7),
    ("Subway",           "5814", "restauration", "fast_food",   10, 4,  "in_store", 0.5),
    ("Panera Bread",     "5814", "restauration", "fast_food",   14, 6,  "both",     0.5),
    ("Olive Garden",     "5812", "restauration", "restaurant",  34, 14, "in_store", 0.5),
    ("Local Diner",      "5812", "restauration", "restaurant",  24, 11, "in_store", 0.6),
    ("DoorDash",         "5812", "restauration", "delivery",    28, 12, "online",   0.9),
    ("Uber Eats",        "5812", "restauration", "delivery",    27, 12, "online",   0.7),
    ("Grubhub",          "5812", "restauration", "delivery",    26, 11, "online",   0.4),
    # Transport
    ("Shell",            "5541", "transport", "fuel",           48, 16, "in_store", 0.9),
    ("Chevron",          "5541", "transport", "fuel",           50, 17, "in_store", 0.7),
    ("ExxonMobil",       "5541", "transport", "fuel",           49, 16, "in_store", 0.7),
    ("Costco Gas",       "5541", "transport", "fuel",           45, 15, "in_store", 0.5),
    ("Uber",             "4121", "transport", "rideshare",      18, 9,  "online",   0.8),
    ("Lyft",             "4121", "transport", "rideshare",      17, 9,  "online",   0.6),
    ("MTA Transit",      "4111", "transport", "transit",        2.9, 0.5, "in_store", 0.6),
    ("SpotHero",         "7523", "transport", "parking",        14, 7,  "both",     0.4),
    ("E-ZPass",          "4784", "transport", "tolls",          12, 7,  "online",   0.5),
    # Utilities
    ("ConEdison",        "4900", "energie", "electricity",      120, 50, "online",  1.0),
    ("PG&E",             "4900", "energie", "electricity",      135, 55, "online",  0.6),
    ("National Grid",    "4900", "energie", "gas",              80, 35, "online",   0.6),
    ("City Water Dept",  "4900", "energie", "water",            55, 22, "online",   0.5),
    # Telecom
    ("Verizon",          "4814", "telecom", "mobile",           75, 12, "online",   0.9),
    ("AT&T",             "4814", "telecom", "mobile",           70, 12, "online",   0.8),
    ("T-Mobile",         "4814", "telecom", "mobile",           60, 10, "online",   0.7),
    ("Xfinity",          "4899", "telecom", "internet_fixe",    70, 15, "online",   0.7),
    # Subscriptions
    ("Netflix",          "4899", "abonnements", "streaming_video",  15.49, 1, "online", 1.0),
    ("Spotify",          "4899", "abonnements", "streaming_music",  11.99, 0, "online", 0.9),
    ("Disney+",          "4899", "abonnements", "streaming_video",  13.99, 0, "online", 0.6),
    ("Hulu",             "4899", "abonnements", "streaming_video",  17.99, 0, "online", 0.5),
    ("Amazon Prime",     "4899", "abonnements", "streaming_video",  14.99, 0, "online", 0.7),
    ("Apple iCloud+",    "4899", "abonnements", "cloud",            2.99, 0, "online", 0.6),
    ("Planet Fitness",   "7997", "abonnements", "gym",             24.99, 2, "in_store", 0.5),
    ("Xbox Game Pass",   "4899", "abonnements", "gaming",          16.99, 0, "online", 0.3),
    ("NYTimes",          "5994", "abonnements", "news",            17.00, 1, "online", 0.3),
    # Shopping
    ("Amazon",           "5942", "shopping", "ecommerce",        42, 30, "online",  1.0),
    ("Best Buy",         "5722", "shopping", "electronics",      110, 70, "both",   0.5),
    ("Apple Store",      "5732", "shopping", "electronics",      240, 190, "both",  0.4),
    ("Home Depot",       "5211", "shopping", "home_improvement", 85, 55, "both",    0.6),
    ("Lowe's",           "5211", "shopping", "home_improvement", 80, 50, "both",    0.5),
    ("IKEA",             "5712", "shopping", "home_decor",       120, 80, "both",   0.4),
    ("Nike",             "5661", "shopping", "footwear",         95, 40, "both",    0.4),
    ("Macy's",           "5651", "shopping", "clothing",         62, 34, "both",    0.5),
    ("H&M",              "5651", "shopping", "clothing",         45, 24, "both",    0.5),
    ("Etsy",             "5699", "shopping", "ecommerce",        34, 22, "online",  0.4),
    ("eBay",             "5942", "shopping", "ecommerce",        40, 28, "online",  0.4),
    # Health
    ("CVS Pharmacy",     "5912", "sante", "pharmacy",            22, 14, "in_store", 0.9),
    ("Walgreens",        "5912", "sante", "pharmacy",            20, 13, "in_store", 0.7),
    ("Family Clinic",    "8011", "sante", "doctor",              45, 18, "in_store", 0.5),
    ("Dental Associates","8021", "sante", "dentist",             120, 70, "in_store", 0.4),
    ("LensCrafters",     "8043", "sante", "optical",             190, 110, "in_store", 0.2),
    # Travel
    ("Airbnb",           "7011", "voyages", "airbnb",            210, 130, "online",  0.6),
    ("Marriott",         "7011", "voyages", "hotel",             180, 100, "online",  0.5),
    ("Booking.com",      "7011", "voyages", "hotel",             165, 95, "online",   0.6),
    ("Delta Air Lines",  "4511", "voyages", "flight",            320, 180, "online",  0.5),
    ("Southwest",        "4511", "voyages", "flight",            180, 110, "online",  0.5),
    ("Amtrak",           "4112", "voyages", "train",             95, 55, "online",    0.3),
    ("AMC Theatres",     "7832", "voyages", "cinema",            16, 5,  "in_store",  0.5),
    # Education / pro / finance
    ("State University", "8220", "education", "tuition",         420, 120, "online",  0.2),
    ("Udemy",            "8299", "education", "online_course",   18, 9,  "online",    0.3),
    ("Coursera",         "8299", "education", "online_course",   49, 14, "online",    0.2),
    ("Adobe",            "5734", "professionnel", "software",    59.99, 0, "online",  0.3),
    ("GitHub",           "5734", "professionnel", "software",    21, 0,  "online",    0.2),
    ("WeWork",           "6513", "professionnel", "coworking",   350, 80, "online",   0.1),
    ("IRS",              "9311", "professionnel", "taxes",       480, 260, "online",  0.5),
    ("Robinhood",        "6211", "finance", "brokerage",         300, 200, "online",  0.3),
    ("Fidelity",         "6211", "finance", "brokerage",         500, 300, "online",  0.3),
)

LABEL_NOISE = {
    "Walmart":   ["WAL-MART", "WALMART", "WM SUPERCENTER", "WAL MART #"],
    "Amazon":    ["AMZN MKTP US", "AMAZON.COM", "AMZN MKTP", "AMAZON PRIME"],
    "Starbucks": ["STARBUCKS", "STARBUCKS #", "SQ *STARBUCKS"],
    "Uber":      ["UBER TRIP", "UBER  *TRIP", "UBER TECHNOLOGIES"],
    "Uber Eats": ["UBER EATS", "UBER *EATS"],
    "Netflix":   ["NETFLIX.COM", "NETFLIX", "NETFLIX INC"],
    "Shell":     ["SHELL OIL", "SHELL SERVICE", "SHELL #"],
    "DoorDash":  ["DD *DOORDASH", "DOORDASH", "DOORDASH*"],
    "Target":    ["TARGET", "TARGET #", "TARGET T-"],
}

LOAN_TYPES = {
    "credit_immobilier": {"amount_mu": 320_000, "amount_sigma": 130_000, "term_months": [180, 240, 360], "rate": (0.055, 0.078)},
    "credit_auto":       {"amount_mu": 28_000,  "amount_sigma": 12_000,  "term_months": [48, 60, 72],     "rate": (0.050, 0.099)},
    "credit_conso":      {"amount_mu": 9_000,   "amount_sigma": 4_500,   "term_months": [24, 36, 48],     "rate": (0.080, 0.160)},
    "credit_perso":      {"amount_mu": 15_000,  "amount_sigma": 7_000,   "term_months": [24, 36, 60],     "rate": (0.070, 0.130)},
    "credit_revolving":  {"amount_mu": 5_000,   "amount_sigma": 3_000,   "term_months": [12, 24, 36],     "rate": (0.180, 0.260)},
}

LOAN_DISPLAY = {
    "credit_immobilier": "Mortgage",
    "credit_auto": "Auto Loan",
    "credit_conso": "Personal Loan",
    "credit_perso": "Personal Loan",
    "credit_revolving": "Credit Line",
}

# (merchant_name, category, subcategory, amount_mu, amount_sigma, freq_months, popularity_by_profile)
SUBSCRIPTION_CATALOG = (
    ("Verizon",        "telecom", "mobile",          75.0, 12.0, 1, {"all": 0.9}),
    ("AT&T",           "telecom", "mobile",          70.0, 12.0, 1, {"all": 0.6}),
    ("T-Mobile",       "telecom", "mobile",          60.0, 10.0, 1, {"all": 0.4}),
    ("Xfinity",        "telecom", "internet_fixe",   70.0, 15.0, 1, {"all": 0.5, "famille": 0.85, "csp_plus": 0.85, "cadre": 0.8}),
    ("Netflix",        "abonnements", "streaming_video",  15.49, 1.0, 1, {"all": 0.55, "etudiant": 0.7, "famille": 0.8}),
    ("Spotify",        "abonnements", "streaming_music",  11.99, 0.0, 1, {"all": 0.45, "etudiant": 0.75, "jeune_actif": 0.75}),
    ("Disney+",        "abonnements", "streaming_video",  13.99, 0.0, 1, {"all": 0.2, "famille": 0.45}),
    ("Hulu",           "abonnements", "streaming_video",  17.99, 0.0, 1, {"all": 0.2}),
    ("Amazon Prime",   "abonnements", "streaming_video",  14.99, 0.0, 1, {"all": 0.4}),
    ("Apple iCloud+",  "abonnements", "cloud",             2.99, 0.0, 1, {"all": 0.25}),
    ("NYTimes",        "abonnements", "news",             17.0, 1.0, 1, {"csp_plus": 0.35, "cadre": 0.25, "retraite": 0.15, "all": 0.05}),
    ("Planet Fitness", "abonnements", "gym",             24.99, 2.0, 1, {"jeune_actif": 0.3, "cadre": 0.2, "all": 0.1}),
    ("Xbox Game Pass", "abonnements", "gaming",          16.99, 0.0, 1, {"etudiant": 0.2, "jeune_actif": 0.15, "all": 0.05}),
    ("ConEdison",      "energie", "electricity",        120.0, 50.0, 1, {"all": 0.95}),
    ("National Grid",  "energie", "gas",                 80.0, 35.0, 1, {"all": 0.45, "famille": 0.7}),
    ("City Water Dept","energie", "water",               55.0, 22.0, 3, {"all": 0.55}),
    ("State Farm",     "logement", "home_insurance",     32.0, 10.0, 1, {"all": 0.6, "famille": 0.95}),
    ("Geico Auto",     "transport", "auto_insurance",    95.0, 30.0, 1, {"all": 0.4, "famille": 0.85, "cadre": 0.7}),
    ("Blue Cross",     "sante", "health_insurance",     180.0, 70.0, 1, {"all": 0.5, "famille": 0.9, "retraite": 0.85}),
    ("Adobe",          "professionnel", "software",      59.99, 0.0, 1, {"freelance": 0.5, "entrepreneur": 0.4, "all": 0.05}),
    ("GitHub",         "professionnel", "software",      21.0, 0.0, 1, {"freelance": 0.3, "entrepreneur": 0.35, "all": 0.05}),
    ("Google Workspace","professionnel", "software",     12.0, 0.0, 1, {"freelance": 0.4, "entrepreneur": 0.55, "all": 0.05}),
)


def _account_identifier(rng: random.Random, bank: dict) -> str:
    return generate_account_number_us(rng, bank.get("bank_code", ""))


def _street(seq: int, rng: random.Random) -> str:
    return f"{100 + seq} {rng.choice(_STREETS)}"


def _postal(region: str, rng: random.Random) -> str:
    return f"{region}{rng.randint(0, 99):02d}"


LOCALE = Locale(
    code="us",
    country_code="US",
    country_name="United States",
    currency="USD",
    faker_locale="en_US",
    income_scale=1.15,
    inflation_by_year=INFLATION_BY_YEAR,
    inflation_baseline_year=2022,
    cities=CITIES,
    family_situations=FAMILY_SITUATIONS,
    professions=PROFESSIONS,
    gender_dist=(("F", 0.51), ("M", 0.49)),
    banks=BANKS,
    preset_bank_index={"retail_mass": 0, "private": 1, "regional": 2, "young_neobank": 3},
    account_type_display={
        AccountRole.CURRENT: "checking",
        AccountRole.INVEST: "brokerage",
        AccountRole.RETIREMENT: "ira",
        AccountRole.JOINT: "joint_checking",
        AccountRole.BUSINESS: "business_checking",
        AccountRole.HOME_SAVINGS: "money_market",
    },
    savings_variants=(("savings", 0.75), ("money_market", 0.25)),
    has_home_savings=False,
    rail_credit="ach_credit",
    rail_debit="ach_debit",
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
    family_display=FAMILY_US,
    make_account_identifier=_account_identifier,
    phone_format=lambda seq: f"+1202555{seq % 10000:04d}",
    street_format=_street,
    postal_for_region=_postal,
)
