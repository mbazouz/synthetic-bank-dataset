"""Locale tests: fr / us / uk / mix produce coherent, localized, deterministic data."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from bank_gen.main import main as generate_main
from bank_gen.transactions import DISCRETIONARY_CATEGORIES
from bank_gen.locales import AccountRole, get_locale

CURRENCY_BY_CODE = {"fr": "EUR", "us": "USD", "uk": "GBP"}


def _generate(tmp: Path, country: str, seed: int = 4242) -> Path:
    out = tmp / country
    rc = generate_main([
        "--country", country, "--customers", "30",
        "--start", "2023-06-01", "--end", "2023-12-31",
        "--output", str(out), "--seed", str(seed),
    ])
    assert rc == 0
    return out


def _rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@pytest.mark.parametrize("country", ["fr", "us", "uk"])
def test_currency_matches_locale(tmp_path: Path, country: str) -> None:
    out = _generate(tmp_path, country)
    currencies = {r["currency"] for r in _rows(out / "transactions.csv")}
    assert currencies == {CURRENCY_BY_CODE[country]}


@pytest.mark.parametrize("country", ["fr", "us", "uk"])
def test_account_types_are_localized(tmp_path: Path, country: str) -> None:
    out = _generate(tmp_path, country)
    loc = get_locale(country)
    allowed = set(loc.account_type_display.values()) | {v[0] for v in loc.savings_variants}
    accounts = _rows(out / "accounts.csv")
    for a in accounts:
        assert a["account_type"] in allowed, f"unexpected type {a['account_type']} for {country}"
        assert a["role"] in AccountRole.ALL
    # every customer must hold exactly the CURRENT role at least once
    assert any(a["role"] == AccountRole.CURRENT for a in accounts)


@pytest.mark.parametrize("country", ["fr", "us", "uk"])
def test_merchant_categories_are_shared_tokens(tmp_path: Path, country: str) -> None:
    """US/UK catalogues must reuse the shared category tokens (else KeyError in the engine)."""
    out = _generate(tmp_path, country)
    loc = get_locale(country)
    cats = {r["merchant_category"] for r in _rows(out / "transactions.csv")}
    known_canonical = set(DISCRETIONARY_CATEGORIES) | {
        "energie", "telecom", "finance", "professionnel", "education",
        "logement", "revenus", "divers",
    }
    # categories may be locale-translated on output, but must all map back to the
    # shared canonical universe (no locale drift / no KeyError in the engine).
    known_display = {loc.tx_category(t) for t in known_canonical}
    assert cats <= known_display, f"unexpected category tokens: {cats - known_display}"
    discretionary_display = {loc.tx_category(t) for t in DISCRETIONARY_CATEGORIES}
    assert cats & discretionary_display, "no discretionary categories produced"


_FRENCH_TOKENS = {
    # categories / subcategories
    "alimentation", "restauration", "voyages", "sante", "abonnements", "energie",
    "logement", "revenus", "loyer", "salaire", "agios", "retrait_dab",
    "virement_interne", "pension_retraite",
    # profiles / risk / segment / family
    "etudiant", "jeune_actif", "cadre", "csp_plus", "retraite", "fragile",
    "prudent", "modere", "dynamique", "offensif", "JEUNE", "FRAGILE",
    "celibataire", "marie", "pacse", "concubinage", "divorce", "veuf",
}


@pytest.mark.parametrize("country", ["us", "uk"])
def test_no_french_tokens_in_us_uk_output(tmp_path: Path, country: str) -> None:
    """en_* datasets must not surface canonical French taxonomy tokens."""
    out = _generate(tmp_path, country)
    cust = _rows(out / "customers.csv")
    for col in ("profile", "risk_appetite", "customer_segment", "family_situation"):
        vals = {r[col] for r in cust}
        assert not (vals & _FRENCH_TOKENS), f"French leak in customers.{col}: {vals & _FRENCH_TOKENS}"
    tx = _rows(out / "transactions.csv")
    for col in ("category", "merchant_category", "subcategory"):
        vals = {r[col] for r in tx}
        assert not (vals & _FRENCH_TOKENS), f"French leak in transactions.{col}: {vals & _FRENCH_TOKENS}"


@pytest.mark.parametrize("country,prefix", [("fr", "FR"), ("uk", "GB")])
def test_iban_shape(tmp_path: Path, country: str, prefix: str) -> None:
    out = _generate(tmp_path, country)
    for a in _rows(out / "accounts.csv"):
        assert a["iban"].startswith(prefix)


def test_us_identifier_is_routing_account(tmp_path: Path) -> None:
    out = _generate(tmp_path, "us")
    for a in _rows(out / "accounts.csv"):
        routing, _, account = a["iban"].partition(" ")
        assert routing.isdigit() and len(routing) == 9
        assert account.isdigit()


def test_mix_is_multi_locale_and_coherent(tmp_path: Path) -> None:
    out = _generate(tmp_path, "mix")
    customers = _rows(out / "customers.csv")
    codes = {c["locale_code"] for c in customers}
    assert len(codes) >= 2, "mix should assign more than one country"
    loc_of = {c["customer_id"]: c["locale_code"] for c in customers}
    for r in _rows(out / "transactions.csv"):
        assert r["currency"] == CURRENCY_BY_CODE[loc_of[r["customer_id"]]]


_FRENCH_COLUMNS = {
    "prenom", "nom", "sexe", "date_naissance", "ville", "code_postal", "pays",
    "situation_familiale", "nombre_enfants", "segment_client", "profil",
    "revenu_mensuel", "patrimoine_estime", "score_financier", "appetence_risque",
    "date_entree_banque", "type_compte", "date_ouverture", "solde_initial",
    "solde_actuel", "autorisation_decouvert", "statut", "libelle", "categorie",
    "sous_categorie", "iban_destinataire", "montant_emprunte", "capital_restant",
    "taux_annuel", "duree_mois", "mensualite", "date_debut", "date_fin",
    "jour_prelevement", "type_credit", "date_emission", "date_expiration",
}


@pytest.mark.parametrize("country", ["fr", "us", "uk"])
def test_raw_headers_are_english(tmp_path: Path, country: str) -> None:
    """The raw output must not carry French column NAMES, in any locale."""
    out = _generate(tmp_path, country)
    for fname in ("customers.csv", "accounts.csv", "cards.csv",
                  "subscriptions.csv", "loans.csv", "transactions.csv"):
        with (out / fname).open(encoding="utf-8") as f:
            header = set(next(csv.reader(f)))
        leak = header & _FRENCH_COLUMNS
        assert not leak, f"French column names in {fname}: {leak}"


def test_no_foreign_by_default(tmp_path: Path) -> None:
    out = _generate(tmp_path, "us")
    rows = _rows(out / "transactions.csv")
    assert all(r["is_foreign"] == "False" for r in rows), "foreign tx leaked with default share=0"
    # the foreign columns still exist and are identity for domestic rows
    sample = rows[0]
    assert sample["original_currency"] == sample["currency"]
    assert sample["fx_rate"] == "1.0" and sample["foreign_fee"] == "0.0"


def test_foreign_transactions(tmp_path: Path) -> None:
    out = out = tmp_path / "fgn"
    rc = generate_main([
        "--country", "us", "--customers", "30", "--foreign-share", "0.12",
        "--start", "2024-01-01", "--end", "2024-06-30",
        "--output", str(out), "--seed", "7",
    ])
    assert rc == 0
    rows = _rows(out / "transactions.csv")
    fgn = [r for r in rows if r["is_foreign"] == "True"]
    assert fgn, "expected some foreign transactions"
    for r in fgn:
        # billing currency must stay the account's home currency (USD here)
        assert r["currency"] == "USD"
        # the original leg is in a different currency, with a non-trivial fx rate
        assert r["original_currency"] != "USD"
        assert float(r["fx_rate"]) != 1.0
        assert float(r["foreign_fee"]) >= 0
        # billed amount = original * fx, plus the markup folded in (all debits)
        expected = round(float(r["original_amount"]) * float(r["fx_rate"]) - float(r["foreign_fee"]), 2)
        assert abs(float(r["amount"]) - expected) < 0.02
    # fees are generally charged (not zero across the board)
    assert sum(float(r["foreign_fee"]) for r in fgn) > 0


def test_determinism_customers_accounts(tmp_path: Path) -> None:
    a = _generate(tmp_path / "a", "mix", seed=999)
    b = _generate(tmp_path / "b", "mix", seed=999)
    for f in ("customers.csv", "accounts.csv"):
        assert (a / f).read_bytes() == (b / f).read_bytes(), f"{f} not deterministic"
