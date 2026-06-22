"""Merchant catalogue: well-known European brands + long-tail local merchants.

Each merchant has:
    name, mcc, category, subcategory, amount_range (mu, sigma in EUR),
    cadence (weekly_share / typical days-of-week, daily_share, monthly_share),
    pos (in_store / online / both), region_scope ('national' | 'capital' | 'south'...)
"""
from __future__ import annotations

import random
from typing import Iterable

# (name, mcc, category, subcategory, amount_mu, amount_sigma, channel, weight)
MERCHANTS_STATIC: list[tuple[str, str, str, str, float, float, str, float]] = [
    # ---- Supermarkets ---------------------------------------------------
    ("Carrefour",        "5411", "alimentation", "supermarche", 58, 32, "both",    1.0),
    ("Leclerc",          "5411", "alimentation", "supermarche", 62, 35, "in_store",1.0),
    ("Auchan",           "5411", "alimentation", "supermarche", 55, 30, "both",    0.9),
    ("Intermarché",      "5411", "alimentation", "supermarche", 50, 28, "in_store",0.9),
    ("Monoprix",         "5411", "alimentation", "supermarche", 42, 18, "both",    0.7),
    ("Lidl",             "5411", "alimentation", "supermarche", 38, 22, "in_store",0.9),
    ("Aldi",             "5411", "alimentation", "supermarche", 36, 19, "in_store",0.6),
    ("Picard",           "5411", "alimentation", "supermarche", 28, 15, "both",    0.5),
    ("Franprix",         "5411", "alimentation", "supermarche", 22, 12, "in_store",0.6),
    ("Carrefour City",   "5411", "alimentation", "supermarche", 18, 11, "in_store",0.7),
    # ---- Boulangerie / petits commerces ---------------------------------
    ("Boulangerie Paul", "5462", "alimentation", "boulangerie",  9,  4, "in_store",0.7),
    ("Boulangerie Marie Blachère","5462","alimentation","boulangerie",10,5,"in_store",0.5),
    ("Boucherie du Marché","5422","alimentation","boucherie",   25, 12, "in_store",0.3),
    ("Le Primeur",       "5411", "alimentation", "primeur",     14,  8, "in_store",0.3),
    # ---- Restauration ---------------------------------------------------
    ("McDonald's",       "5814", "restauration", "fast_food",   12,  5, "both",    1.0),
    ("Burger King",      "5814", "restauration", "fast_food",   13,  5, "both",    0.7),
    ("KFC",              "5814", "restauration", "fast_food",   14,  6, "both",    0.6),
    ("Subway",           "5814", "restauration", "fast_food",   10,  4, "in_store",0.4),
    ("Starbucks",        "5814", "restauration", "cafe_bar",     8,  3, "in_store",0.4),
    ("Brioche Dorée",    "5814", "restauration", "fast_food",   11,  4, "in_store",0.3),
    ("Bistrot du Coin",  "5812", "restauration", "restaurant",  28, 12, "in_store",0.7),
    ("Pizza Hut",        "5812", "restauration", "restaurant",  22,  9, "both",    0.4),
    ("Sushi Shop",       "5812", "restauration", "restaurant",  26, 10, "both",    0.4),
    ("Le Petit Café",    "5812", "restauration", "cafe_bar",     6,  3, "in_store",0.6),
    ("Le Comptoir Lyonnais","5812","restauration","restaurant", 35, 14, "in_store",0.4),
    ("Uber Eats",        "5812", "restauration", "livraison",   24, 11, "online",  0.9),
    ("Deliveroo",        "5812", "restauration", "livraison",   26, 11, "online",  0.6),
    ("Just Eat",         "5812", "restauration", "livraison",   23, 10, "online",  0.5),
    # ---- Transport ------------------------------------------------------
    ("SNCF Connect",     "4112", "transport", "sncf",            65, 45, "online",  0.9),
    ("RATP",             "4111", "transport", "metro_bus",       2.10, 0.6,"in_store",0.9),
    ("Île-de-France Mobilités","4111","transport","metro_bus",   84.10,0.0,"online",0.4),
    ("Uber",             "4121", "transport", "uber_vtc",        15,  8, "online",  0.7),
    ("Bolt",             "4121", "transport", "uber_vtc",        13,  7, "online",  0.4),
    ("Heetch",           "4121", "transport", "uber_vtc",        12,  7, "online",  0.3),
    ("Total Énergies",   "5541", "transport", "carburant",       55, 18, "in_store",0.9),
    ("TotalEnergies",    "5541", "transport", "carburant",       57, 19, "in_store",0.4),
    ("Esso",             "5541", "transport", "carburant",       52, 17, "in_store",0.5),
    ("Shell",            "5541", "transport", "carburant",       58, 18, "in_store",0.5),
    ("BP",               "5541", "transport", "carburant",       56, 17, "in_store",0.3),
    ("Carrefour Energies","5541","transport", "carburant",       50, 17, "in_store",0.6),
    ("Vinci Autoroutes", "4784", "transport", "peage",           18, 10, "online",  0.6),
    ("APRR",             "4784", "transport", "peage",           14,  8, "online",  0.3),
    ("Indigo",           "7523", "transport", "parking",          7,  3, "both",    0.6),
    ("Q-Park",           "7523", "transport", "parking",         12,  6, "in_store",0.3),
    ("BlaBlaCar",        "4789", "transport", "sncf",            32, 16, "online",  0.4),
    ("Lime",             "4121", "transport", "velo",             4,  2, "online",  0.3),
    # ---- Énergie / utilities -------------------------------------------
    ("EDF",              "4900", "energie", "electricite",       95, 40, "online", 1.0),
    ("Engie",            "4900", "energie", "gaz",               75, 35, "online", 0.7),
    ("TotalEnergies Pro","4900", "energie", "electricite",       89, 38, "online", 0.4),
    ("Eau de Paris",     "4900", "energie", "eau",               42, 20, "online", 0.3),
    ("Veolia",           "4900", "energie", "eau",               45, 22, "online", 0.6),
    # ---- Télécom --------------------------------------------------------
    ("Free Mobile",      "4814", "telecom", "mobile",            15.99,  0,"online",0.9),
    ("Free",             "4899", "telecom", "internet_fixe",     29.99,  0,"online",0.7),
    ("Orange",           "4814", "telecom", "mobile",            24.99,  3,"online",0.9),
    ("Orange Internet",  "4899", "telecom", "internet_fixe",     39.99,  4,"online",0.6),
    ("SFR",              "4814", "telecom", "mobile",            19.99,  3,"online",0.5),
    ("Bouygues Telecom", "4814", "telecom", "mobile",            17.99,  3,"online",0.5),
    ("Sosh",             "4814", "telecom", "mobile",            14.99,  2,"online",0.4),
    # ---- Streaming / abos ----------------------------------------------
    ("Netflix",          "4899", "abonnements", "streaming_video", 13.49, 1, "online",1.0),
    ("Spotify",          "4899", "abonnements", "streaming_musique",10.99,0,"online",0.9),
    ("Deezer",           "4899", "abonnements", "streaming_musique", 9.99,0,"online",0.4),
    ("Disney+",          "4899", "abonnements", "streaming_video",  8.99,0,"online",0.6),
    ("Amazon Prime",     "4899", "abonnements", "streaming_video",  6.99,0,"online",0.7),
    ("Apple One",        "4899", "abonnements", "streaming_video", 16.99,2,"online",0.4),
    ("YouTube Premium",  "4899", "abonnements", "streaming_video", 11.99,0,"online",0.4),
    ("Canal+",           "4899", "abonnements", "streaming_video", 24.99,3,"online",0.4),
    ("Le Monde",         "5994", "abonnements", "presse",          12.90,1,"online",0.3),
    ("Mediapart",        "5994", "abonnements", "presse",          11.00,0,"online",0.2),
    ("iCloud+",          "4899", "abonnements", "cloud",            2.99,0,"online",0.6),
    ("Google One",       "4899", "abonnements", "cloud",            1.99,0,"online",0.4),
    ("Basic Fit",        "7997", "abonnements", "salle_sport",     24.99,2,"in_store",0.5),
    ("Fitness Park",     "7997", "abonnements", "salle_sport",     19.99,2,"in_store",0.4),
    ("PlayStation Plus", "4899", "abonnements", "gaming",           8.99,0,"online",0.3),
    ("Xbox Game Pass",   "4899", "abonnements", "gaming",          12.99,0,"online",0.3),
    ("Steam",            "5734", "abonnements", "gaming",          24.00,18,"online",0.5),
    # ---- Shopping -------------------------------------------------------
    ("Amazon",           "5942", "shopping", "ecommerce",          38, 28, "online",1.0),
    ("Cdiscount",        "5942", "shopping", "ecommerce",          45, 32, "online",0.5),
    ("Fnac",             "5942", "shopping", "electronique",       65, 42, "both",  0.7),
    ("Darty",            "5722", "shopping", "electronique",       95, 60, "both",  0.5),
    ("Boulanger",        "5722", "shopping", "electronique",       85, 55, "both",  0.4),
    ("Apple Store",      "5732", "shopping", "electronique",      220,180, "both",  0.4),
    ("FNAC Spectacles",  "7929", "shopping", "ecommerce",          35, 15, "online",0.3),
    ("Decathlon",        "5941", "shopping", "ecommerce",          55, 35, "both",  0.7),
    ("Zara",             "5651", "shopping", "vetements",          58, 32, "both",  0.7),
    ("H&M",              "5651", "shopping", "vetements",          45, 25, "both",  0.6),
    ("Uniqlo",           "5651", "shopping", "vetements",          55, 28, "both",  0.4),
    ("Kiabi",            "5651", "shopping", "vetements",          35, 18, "both",  0.5),
    ("Nike",             "5661", "shopping", "chaussures",         95, 40, "both",  0.4),
    ("Adidas",           "5661", "shopping", "chaussures",         92, 38, "both",  0.4),
    ("Ikea",             "5712", "shopping", "maison_deco",       115, 80, "both",  0.5),
    ("Maisons du Monde", "5712", "shopping", "maison_deco",        65, 38, "both",  0.3),
    ("Leroy Merlin",     "5211", "shopping", "maison_deco",        75, 50, "both",  0.6),
    ("Castorama",        "5211", "shopping", "maison_deco",        72, 48, "both",  0.5),
    ("Brico Dépôt",      "5211", "shopping", "maison_deco",        62, 42, "in_store",0.4),
    ("Sephora",          "5977", "shopping", "ecommerce",          45, 22, "both",  0.5),
    ("Yves Rocher",      "5977", "shopping", "ecommerce",          38, 18, "both",  0.3),
    ("Fnac Livres",      "5942", "shopping", "librairie",          22, 10, "both",  0.3),
    ("Cultura",          "5942", "shopping", "librairie",          25, 12, "both",  0.3),
    ("La Grande Récré",  "5945", "shopping", "jouets",             32, 18, "both",  0.3),
    ("Smyths Toys",      "5945", "shopping", "jouets",             45, 25, "both",  0.2),
    # ---- Santé ----------------------------------------------------------
    ("Pharmacie Centrale","5912","sante", "pharmacie",             18, 12, "in_store",0.9),
    ("Pharmacie Lafayette","5912","sante","pharmacie",             22, 14, "in_store",0.6),
    ("Doctolib",         "8062", "sante", "medecin",               25,  8, "online",  0.4),
    ("Cabinet médical",  "8011", "sante", "medecin",               25,  6, "in_store",0.6),
    ("Cabinet dentaire", "8021", "sante", "dentiste",              75, 45, "in_store",0.4),
    ("Optic 2000",       "8043", "sante", "optique",              220,120, "in_store",0.2),
    ("Krys",             "8043", "sante", "optique",              210,110, "in_store",0.2),
    ("Hôpital Cochin",   "8062", "sante", "hopital",               45, 25, "in_store",0.1),
    # ---- Voyages / loisirs ---------------------------------------------
    ("Airbnb",           "7011", "voyages", "airbnb",             185,120, "online", 0.6),
    ("Booking.com",      "7011", "voyages", "hotel",              155, 95, "online", 0.7),
    ("Hotels.com",       "7011", "voyages", "hotel",              160, 90, "online", 0.3),
    ("Air France",       "4511", "voyages", "billet_avion",       320,180, "online", 0.4),
    ("EasyJet",          "4511", "voyages", "billet_avion",        85, 55, "online", 0.4),
    ("Ryanair",          "4511", "voyages", "billet_avion",        65, 50, "online", 0.4),
    ("Transavia",        "4511", "voyages", "billet_avion",       120, 80, "online", 0.2),
    ("Eurostar",         "4112", "voyages", "billet_train",       145, 85, "online", 0.2),
    ("Trainline",        "4112", "voyages", "billet_train",        55, 28, "online", 0.3),
    ("Club Med",         "4722", "voyages", "agence_voyage",     1450,800, "online", 0.1),
    ("Center Parcs",     "7011", "voyages", "agence_voyage",      580,250, "online", 0.2),
    ("Decathlon Loisirs","5941", "voyages", "sport_loisir",        45, 22, "both",   0.4),
    ("UGC",              "7832", "voyages", "musee_cinema",        11,  3, "in_store",0.5),
    ("Pathé",            "7832", "voyages", "musee_cinema",        13,  3, "in_store",0.4),
    ("MK2",              "7832", "voyages", "musee_cinema",        12,  3, "in_store",0.3),
    ("Louvre",           "7991", "voyages", "musee_cinema",        17,  0, "in_store",0.1),
    ("FNAC Spectacles Concert","7929","voyages","loisirs_culture", 65, 40,"online",  0.3),
    # ---- Famille / éducation -------------------------------------------
    ("École privée",     "8211", "education", "frais_scolaires",  280,150, "online",  0.2),
    ("Crèche Babilou",   "8351", "education", "creche",           650, 80, "online",  0.2),
    ("Centre aéré",      "8351", "education", "garde_enfant",      85, 35, "in_store",0.3),
    ("Université",       "8220", "education", "etudes_sup",       170, 25, "online",  0.2),
    ("Udemy",            "8299", "education", "formation",         18,  9, "online",  0.3),
    ("OpenClassrooms",   "8299", "education", "formation",         24, 14, "online",  0.2),
    # ---- Professionnel (freelance/entrepreneur) ------------------------
    ("URSSAF",           "9311", "professionnel", "urssaf",       420,220, "online",  0.9),
    ("Notion",           "5734", "professionnel", "logiciels_pro",  9,  0, "online",  0.3),
    ("Slack",            "5734", "professionnel", "logiciels_pro", 12.5,0,"online",   0.3),
    ("Adobe Creative Cloud","5734","professionnel","logiciels_pro",59.99,0,"online",  0.3),
    ("Google Workspace", "5734", "professionnel", "logiciels_pro",  9.36,0,"online",  0.3),
    ("OVHcloud",         "5734", "professionnel", "logiciels_pro", 18,  9, "online",  0.3),
    ("WeWork",           "6513", "professionnel", "deplacement_pro",380,80,"online",  0.1),
    # ---- Finance / banque ----------------------------------------------
    ("Banque Atlas - Frais","6012","finance","frais_bancaires",     6.50,0,"online",1.0),
    ("Banque Atlas - Agios","6012","finance","agios",              12.5,8, "online", 0.4),
    ("Boursorama",       "6211", "finance", "investissement_pea",  500,300,"online",  0.3),
    ("Trade Republic",   "6211", "finance", "investissement_pea",  150,80, "online",  0.3),
    ("Yomoni",           "6211", "finance", "assurance_vie",       200,100,"online",  0.2),
    ("Linxea",           "6211", "finance", "assurance_vie",       250,150,"online",  0.2),
    # ---- Marketplaces longue traîne -----------------------------------
    ("Vinted",           "5699", "shopping", "ecommerce",           24, 18, "online", 0.6),
    ("Leboncoin",        "5699", "shopping", "ecommerce",           55, 50, "online", 0.5),
    ("eBay",             "5942", "shopping", "ecommerce",           42, 30, "online", 0.3),
    ("AliExpress",       "5942", "shopping", "ecommerce",           18, 12, "online", 0.4),
]

# Some misspellings / variants to simulate noisy bank labels
LABEL_NOISE = {
    "Carrefour": ["CARREFOUR", "CARREFOUR MARKET", "CRF EXPRESS", "CARREFOUR  CITY 75", "CARREFOR"],
    "Leclerc":   ["LECLERC", "E.LECLERC", "LECLERC DRIVE", "LECLERC MAG"],
    "Uber":      ["UBER BV", "UBER  TRIP", "UBER*RIDE", "UBER TRIP HELP.UBER.COM"],
    "Uber Eats": ["UBER * EATS", "UBER EATS HELP.UBER", "UBER EATS"],
    "Amazon":    ["AMZN MKTP", "AMAZON.FR", "AMZN MKTPL", "AMAZON EU"],
    "Netflix":   ["NETFLIX.COM", "NETFLIX SARL", "NETFLIX"],
    "Spotify":   ["SPOTIFY P", "SPOTIFY AB", "SPOTIFY"],
    "SNCF Connect": ["SNCF CONNECT", "SNCF-CONNECT.COM", "SNCF VOYAGEURS"],
    "EDF":       ["EDF SA", "EDF FACT", "EDF CLIENT"],
    "Free Mobile":["FREE MOBILE", "FREE-MOBILE", "FREEMOB"],
    "Total Énergies":["TOTAL ENERGIES", "TOTALENERGIES", "TOTAL ACCESS", "TOTAL STATION"],
}


def label_for(merchant_name: str, rng: random.Random, noise: dict | None = None) -> str:
    """Return a bank-statement label for a merchant.

    A given merchant maps to a SMALL, stable set of label variants (the curated
    `noise` list for that locale, else the uppercased name). We deliberately do
    NOT append a random per-transaction number or truncate to a random length:
    that would make every payment to the same merchant a distinct string,
    exploding the distinct-label cardinality into the 100k+ range and turning
    the downstream label-embedding step into meaningless noise (and blowing its
    time budget). Real statement labels for a merchant are highly repetitive,
    so this is also more realistic.
    """
    variants = (noise if noise is not None else LABEL_NOISE).get(merchant_name)
    if variants:
        return rng.choice(variants)
    return merchant_name.upper()


def build_merchant_pools(merchants: Iterable[tuple]) -> dict[str, list[dict]]:
    """Group a merchant catalogue by category into sampling pools."""
    pools: dict[str, list[dict]] = {}
    for row in merchants:
        name, mcc, cat, sub, mu, sd, channel, weight = row
        pools.setdefault(cat, []).append({
            "name": name, "mcc": mcc, "subcategory": sub,
            "amount_mu": mu, "amount_sigma": sd, "channel": channel, "weight": weight,
        })
    return pools


def iter_merchants(merchants: Iterable[tuple] = MERCHANTS_STATIC) -> Iterable[dict]:
    for i, row in enumerate(merchants):
        name, mcc, cat, sub, mu, sd, channel, weight = row
        yield {
            "merchant_id": f"M{i+1:05d}",
            "name": name,
            "mcc": mcc,
            "category": cat,
            "subcategory": sub,
            "amount_mu": mu,
            "amount_sigma": sd,
            "channel": channel,
            "weight": weight,
        }
