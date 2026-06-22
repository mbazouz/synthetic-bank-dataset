"""Transaction engine.

Generates a stream of transactions for each customer, day by day, respecting:
  * salary credits (incl. variability for freelancers/entrepreneurs)
  * rent and recurring real-estate / utility / insurance / streaming debits
  * loan installments
  * daily discretionary spending biased by profile
  * seasonal patterns (December gifts, summer travel, back-to-school...)
  * yearly inflation on recurring amounts
  * cash withdrawals at ATM
  * automatic savings transfer at month end
  * life events (one-shot extras, salary changes, activity shifts)
  * overdraft / agios anomalies
  * minor label noise

The engine is a *generator*: it yields transaction dicts so the caller can
flush them to disk in chunks. Each customer's account balances are kept in
local state — no global aggregation is needed.
"""
from __future__ import annotations

import random
import uuid
from calendar import monthrange
from datetime import date, datetime, time, timedelta
from typing import Iterable, Iterator

import numpy as np

from .accounts import Account
from .config import BANK_PRESETS
from .customers import Customer
from .loans import Loan
from .locales import AccountRole, BankPresetSpec, Locale, get_locale
from .merchants import build_merchant_pools, label_for
from .profiles import PROFILES, ProfileSpec
from .subscriptions import Subscription
from .trajectory import Trajectory, generate_trajectory


# Per-category merchant pools, cached per locale code (built on first use).
_MERCHANT_POOLS_CACHE: dict[str, dict[str, list[dict]]] = {}


def _pools_for(locale: Locale) -> dict[str, list[dict]]:
    pools = _MERCHANT_POOLS_CACHE.get(locale.code)
    if pools is None:
        pools = build_merchant_pools(locale.merchants)
        _MERCHANT_POOLS_CACHE[locale.code] = pools
    return pools


_MCC_BY_NAME_CACHE: dict[str, dict[str, str]] = {}


def _mcc_for(locale: Locale, name: str) -> str:
    table = _MCC_BY_NAME_CACHE.get(locale.code)
    if table is None:
        table = {row[0]: row[1] for row in locale.merchants}
        _MCC_BY_NAME_CACHE[locale.code] = table
    return table.get(name, "4899")


DISCRETIONARY_CATEGORIES = [
    "alimentation", "restauration", "transport", "shopping",
    "voyages", "sante", "abonnements",
]

# Baseline weight of each discretionary category in a daily basket
BASELINE_CATEGORY_WEIGHTS = {
    "alimentation": 4.0,
    "restauration": 2.5,
    "transport":    2.0,
    "shopping":     1.5,
    "voyages":      0.6,
    "sante":        0.8,
    "abonnements":  0.4,  # most abonnements come from the subscription table
}


def _inflation_factor(d: date, baseline_year: int, table: dict[int, float]) -> float:
    """Cumulative inflation from baseline_year up to year of d."""
    f = 1.0
    for y in range(baseline_year + 1, d.year + 1):
        f *= (1 + table.get(y, 0.02))
    return f


def _seasonal_multiplier(d: date, category: str) -> float:
    m = d.month
    if category == "voyages":
        if m in (7, 8): return 2.0
        if m in (6, 9, 12): return 1.4
        if m in (2,): return 1.1
        return 0.7
    if category == "shopping":
        if m == 12: return 1.9
        if m in (1, 7): return 1.4  # soldes
        if m == 9: return 1.3       # rentrée
        return 1.0
    if category == "alimentation":
        if m == 12: return 1.2
        return 1.0
    if category == "restauration":
        if m in (6, 7, 8, 12): return 1.2
        return 1.0
    if category == "transport":
        if m in (7, 8, 12): return 1.2
        return 1.0
    return 1.0


def _weekend_boost(d: date, category: str) -> float:
    if d.weekday() >= 5:  # sat/sun
        if category in ("restauration", "voyages", "shopping"):
            return 1.6
        if category in ("alimentation", "transport"):
            return 1.2
    return 1.0


def _pick_merchant(pools: dict[str, list[dict]], category: str, rng: random.Random) -> dict:
    pool = pools[category]
    weights = [m["weight"] for m in pool]
    return rng.choices(pool, weights=weights, k=1)[0]


def _amount_from_merchant(m: dict, rng_np: np.random.Generator, sign: int = -1) -> float:
    mu = m["amount_mu"]
    sigma = max(0.01, m["amount_sigma"])
    a = float(rng_np.normal(mu, sigma))
    a = max(0.5, a)  # never zero
    return round(sign * a, 2)


def _channel_to_tx_type(channel: str, rng: random.Random) -> tuple[str, str]:
    """Return (transaction_type, payment_channel)."""
    if channel == "online":
        return "card_payment_online", "online"
    if channel == "in_store":
        if rng.random() < 0.55:
            return "card_payment_contactless", "contactless"
        return "card_payment", "in_store"
    # 'both'
    r = rng.random()
    if r < 0.4:
        return "card_payment_online", "online"
    if r < 0.8:
        return "card_payment_contactless", "contactless"
    return "card_payment", "in_store"


def _make_tx(
    account: Account,
    when: datetime,
    amount: float,
    merchant_name: str,
    mcc: str,
    category: str,
    subcategory: str,
    tx_type: str,
    channel: str,
    label: str,
    *,
    is_subscription: bool = False,
    is_salary: bool = False,
    is_transfer: bool = False,
    is_cash_withdrawal: bool = False,
    iban_destinataire: str | None = None,
    city: str | None = None,
    currency: str = "EUR",
    country: str = "FR",
    balance_after: float = 0.0,
) -> dict:
    return {
        "transaction_id": uuid.uuid4().hex,
        "account_id": account.account_id,
        "customer_id": account.customer_id,
        "timestamp": when.isoformat(timespec="seconds"),
        "amount": round(amount, 2),
        "currency": currency,
        "merchant_name": merchant_name,
        "merchant_category": category,
        "merchant_mcc": mcc,
        "transaction_type": tx_type,
        "payment_channel": channel,
        "city": city or "",
        "country": country,
        "counterparty_iban": iban_destinataire or "",
        "label": label,
        "category": category,
        "subcategory": subcategory,
        "is_subscription": is_subscription,
        "is_salary": is_salary,
        "is_transfer": is_transfer,
        "is_cash_withdrawal": is_cash_withdrawal,
        "balance_after_transaction": round(balance_after, 2),
    }


def _random_time(d: date, category: str, rng: random.Random) -> datetime:
    """Pick a plausible time-of-day for the transaction."""
    if category in ("restauration",):
        # lunch and dinner peaks
        hour = rng.choices(range(0, 24), weights=[
            0.3,0.2,0.1,0.1,0.1,0.1,0.5,1.0,2.0,3.0,
            3.5,5.5,8.0,7.0,4.0,3.0,3.5,5.0,7.0,7.5,
            5.0,3.0,1.5,0.7], k=1)[0]
    elif category == "transport":
        hour = rng.choices(range(0, 24), weights=[
            0.5,0.3,0.2,0.2,0.3,1.0,3.0,5.5,7.0,4.0,
            2.5,2.5,3.0,3.0,3.0,3.5,5.0,7.0,6.0,3.5,
            2.5,1.5,1.0,0.7], k=1)[0]
    elif category == "alimentation":
        hour = rng.choices(range(0, 24), weights=[
            0.1,0.1,0.1,0.1,0.1,0.2,0.6,1.5,2.5,3.0,
            4.0,5.0,4.0,3.5,3.0,3.5,4.5,6.0,7.0,4.0,
            2.0,1.0,0.5,0.2], k=1)[0]
    else:
        hour = rng.randint(7, 22)
    minute = rng.randint(0, 59)
    second = rng.randint(0, 59)
    return datetime.combine(d, time(hour, minute, second))


DECLINE_RATIO = 1.3  # Refuse debits that would push balance below -1.3 * authorised overdraft.


def _safe_post(account: Account, amount: float) -> tuple[float, bool, bool]:
    """Apply amount to account. Returns (new_balance, overdraft_flag, posted_flag).

    The account balance can dip below zero up to the authorised overdraft.
    Beyond ~1.3 × authorised overdraft we *decline* the payment (banks do too)
    so the dataset never shows physically impossible balances.
    """
    new_balance = account.solde_actuel + amount
    if amount < 0 and new_balance < -account.autorisation_decouvert * DECLINE_RATIO:
        # Refuse the debit: do NOT mutate the balance and do NOT post the tx.
        return account.solde_actuel, False, False
    over = new_balance < -account.autorisation_decouvert
    account.solde_actuel = new_balance
    return new_balance, over, True


# ---------------------------------------------------------------------------
# Per-customer engine
# ---------------------------------------------------------------------------

def _state_for_customer(
    customer: Customer,
    accounts: list[Account],
    subs: list[Subscription],
    loans: list[Loan],
    phases: list,
    rng_np: np.random.Generator,
    locale: Locale,
) -> dict:
    main = next((a for a in accounts if a.role == AccountRole.CURRENT), accounts[0])
    savings = [a for a in accounts if a.role in AccountRole.SWEEP_TARGETS]
    pro = next((a for a in accounts if a.role == AccountRole.BUSINESS), None)
    joint = next((a for a in accounts if a.role == AccountRole.JOINT), None)

    salary_day = int(rng_np.integers(25, 29))  # paid 25-28th
    rent_day = int(rng_np.integers(1, 6))
    # One stable employer name per customer (kept out of the per-payment label so
    # salary credits don't each become a distinct label string).
    employer = locale.labels.employer(int(rng_np.integers(100, 1000)))

    p0 = phases[0]
    active_profile = PROFILES[p0.profile_name]
    return {
        "locale": locale,
        "currency": locale.currency,
        "country": locale.country_code,
        "labels": locale.labels,
        "pools": _pools_for(locale),
        "inflation_table": locale.inflation_by_year,
        "inflation_baseline": locale.inflation_baseline_year,
        "income_scale": locale.income_scale,
        "main": main,
        "savings_accounts": savings,
        "pro": pro,
        "joint": joint,
        "subs": subs,
        "loans": loans,
        "phases": phases,
        "phase_idx": 0,
        # phase-driven, re-bound by _advance_phase as the day-loop crosses boundaries
        "active_profile": active_profile,
        "salary": p0.monthly_income,
        "rent": round(p0.monthly_income * active_profile.rent_ratio, 2) if active_profile.rent_ratio > 0 else 0.0,
        "leisure_bias": p0.leisure_bias,
        "activity_multiplier": p0.activity_multiplier,
        "status": p0.status,
        "salary_day": salary_day,
        "rent_day": rent_day,
        "employer": employer,
        "freelance": active_profile.name in ("freelance", "entrepreneur"),
    }


def _emit_salary(
    state: dict, customer: Customer, profile: ProfileSpec, d: date, rng: random.Random, rng_np: np.random.Generator,
) -> list[dict]:
    # No income in a deceased/dormant phase — standing orders keep draining the
    # account until rejection (the "arrêt brusque, que des prélèvements" signal).
    if state["status"] != "active":
        return []
    main = state["main"]
    lbl = state["labels"]
    cur, ctry = state["currency"], state["country"]
    rail_c = state["locale"].rail_credit
    inflation = _inflation_factor(d, state["inflation_baseline"], state["inflation_table"])
    base = state["salary"] * inflation
    # Freelancers: irregular both in date and amount
    txs: list[dict] = []
    if state["freelance"]:
        # 1-3 invoices per month, varying dates
        n_invoices = rng.choices([1, 2, 3], weights=[0.45, 0.40, 0.15], k=1)[0]
        for _ in range(n_invoices):
            amount = float(np.clip(rng_np.normal(base / n_invoices, base * 0.35),
                                   base * 0.1, base * 2.0))
            when = _random_time(d, "revenus", rng)
            new_bal, _, _ = _safe_post(main, +amount)
            txs.append(_make_tx(
                main, when, +amount, lbl.freelance_merchant, "0000", "revenus", "freelance",
                rail_c, "transfer", lbl.freelance_label,
                is_salary=True, currency=cur, country=ctry, balance_after=new_bal,
            ))
    else:
        # Stable salary with small variance (primes, bonus quarter)
        sigma = base * 0.04
        if d.month in (3, 12):
            base *= rng.uniform(1.0, 1.10)  # prime / 13e mois
        amount = float(np.clip(rng_np.normal(base, sigma), base * 0.85, base * 1.20))
        when = _random_time(d, "revenus", rng)
        new_bal, _, _ = _safe_post(main, +amount)
        is_retraite = state["active_profile"].name == "retraite"
        payer = lbl.pension_payer if is_retraite else state["employer"]
        txs.append(_make_tx(
            main, when, +amount, payer, "0000", "revenus",
            "pension_retraite" if is_retraite else "salaire",
            rail_c, "transfer",
            lbl.salary_label(payer), is_salary=True, currency=cur, country=ctry, balance_after=new_bal,
        ))
        # Auto-savings transfer on the same day (if an OPEN savings account exists)
        open_savings = [a for a in state["savings_accounts"] if a.date_ouverture <= d]
        if open_savings and profile.savings_rate > 0:
            sav_amount = round(amount * profile.savings_rate * rng.uniform(0.5, 1.0), 2)
            if sav_amount > 5:
                sav_acc = rng.choice(open_savings)
                new_main, _, posted = _safe_post(main, -sav_amount)
                if posted:
                    new_sav, _, _ = _safe_post(sav_acc, +sav_amount)
                    txs.append(_make_tx(
                        main, when + timedelta(minutes=1), -sav_amount, lbl.savings_out_merchant,
                        "0000", "finance", "virement_interne", "internal_transfer", "transfer",
                        lbl.savings_out_label(sav_acc.type_compte),
                        is_transfer=True, iban_destinataire=sav_acc.iban,
                        currency=cur, country=ctry, balance_after=new_main,
                    ))
                    txs.append(_make_tx(
                        sav_acc, when + timedelta(minutes=1), +sav_amount, lbl.savings_in_merchant,
                        "0000", "finance", "virement_interne", "internal_transfer", "transfer",
                        lbl.savings_in_label, is_transfer=True, iban_destinataire=main.iban,
                        currency=cur, country=ctry, balance_after=new_sav,
                    ))
    return txs


def _emit_rent(state: dict, d: date, rng: random.Random) -> list[dict]:
    if state["rent"] <= 0:
        return []
    main = state["main"]
    lbl = state["labels"]
    cur, ctry = state["currency"], state["country"]
    amt = state["rent"] * _inflation_factor(d, state["inflation_baseline"], state["inflation_table"])
    when = _random_time(d, "logement", rng)
    bailleur = rng.choice(lbl.landlords)
    new_bal, _, posted = _safe_post(main, -amt)
    if posted:
        return [_make_tx(
            main, when, -amt, bailleur, "6513", "logement", "loyer",
            state["locale"].rail_debit, "direct_debit",
            lbl.rent_label,
            currency=cur, country=ctry, balance_after=new_bal,
        )]
    # Direct debit rejected — emit a small fee transaction so analysts see the signal.
    fee = 20.0
    fee_bal, _, _ = _safe_post(main, -fee)
    return [_make_tx(
        main, when, -fee, lbl.reject_merchant(main.bank_name),
        "6012", "finance", "agios", "fee", "direct_debit",
        lbl.reject_rent_label, currency=cur, country=ctry, balance_after=fee_bal,
    )]


def _emit_subscriptions(state: dict, d: date, rng: random.Random) -> list[dict]:
    txs: list[dict] = []
    lbl = state["labels"]
    cur, ctry = state["currency"], state["country"]
    loc = state["locale"]
    for sub in state["subs"]:
        if sub.start_date > d or (sub.end_date and sub.end_date < d):
            continue
        # Recurrence
        months_since = (d.year - sub.start_date.year) * 12 + (d.month - sub.start_date.month)
        if months_since < 0 or months_since % sub.frequency_months != 0:
            continue
        if d.day != min(sub.billing_day, monthrange(d.year, d.month)[1]):
            continue
        # Pick the right account. If the targeted secondary account is not yet
        # open at d, fall back to the main account — banks roll subscriptions
        # over to the available account, they don't sit in limbo.
        target_acc = state["main"] if sub.account_id == state["main"].account_id else None
        if target_acc is None and state["pro"] and sub.account_id == state["pro"].account_id:
            target_acc = state["pro"] if state["pro"].date_ouverture <= d else state["main"]
        if target_acc is None:
            target_acc = state["main"]
        amount = sub.amount * _inflation_factor(d, state["inflation_baseline"], state["inflation_table"])
        when = _random_time(d, sub.category, rng)
        mcc = _mcc_for(loc, sub.merchant_name)
        new_bal, _, posted = _safe_post(target_acc, -amount)
        if posted:
            txs.append(_make_tx(
                target_acc, when, -amount, sub.merchant_name, mcc,
                sub.category, sub.subcategory,
                loc.rail_debit, "direct_debit",
                label_for(sub.merchant_name, rng, loc.label_noise),
                is_subscription=True, currency=cur, country=ctry, balance_after=new_bal,
            ))
        else:
            fee = 18.0
            fee_bal, _, _ = _safe_post(target_acc, -fee)
            txs.append(_make_tx(
                target_acc, when, -fee, lbl.reject_merchant(target_acc.bank_name),
                "6012", "finance", "agios", "fee", "direct_debit",
                lbl.reject_sub_label(sub.merchant_name),
                currency=cur, country=ctry, balance_after=fee_bal,
            ))
    return txs


def _emit_loans(state: dict, d: date, rng: random.Random) -> list[dict]:
    txs: list[dict] = []
    main = state["main"]
    lbl = state["labels"]
    cur, ctry = state["currency"], state["country"]
    loc = state["locale"]
    for loan in state["loans"]:
        if d < loan.date_debut or d > loan.date_fin:
            continue
        if d.day != min(loan.jour_prelevement, monthrange(d.year, d.month)[1]):
            continue
        amt = loan.mensualite
        when = _random_time(d, "finance", rng)
        subcat = {
            "credit_immobilier": "credit_immobilier",
            "credit_auto": "credit_auto",
            "credit_conso": "credit_conso",
            "credit_perso": "credit_conso",
            "credit_revolving": "credit_conso",
        }.get(loan.type_credit, "credit_conso")
        disp = loc.loan_display.get(loan.type_credit, loan.type_credit.replace("_", " ").title())
        new_bal, _, posted = _safe_post(main, -amt)
        if posted:
            txs.append(_make_tx(
                main, when, -amt,
                lbl.loan_merchant(main.bank_name, disp),
                "6012", "finance", subcat,
                loc.rail_debit, "direct_debit",
                lbl.loan_label(disp), currency=cur, country=ctry, balance_after=new_bal,
            ))
        else:
            fee = 25.0
            fee_bal, _, _ = _safe_post(main, -fee)
            txs.append(_make_tx(
                main, when, -fee, lbl.reject_merchant(main.bank_name),
                "6012", "finance", "agios", "fee", "direct_debit",
                lbl.reject_loan_label(loan.loan_id), currency=cur, country=ctry, balance_after=fee_bal,
            ))
    return txs


def _emit_daily_spend(
    state: dict, customer: Customer, profile: ProfileSpec, d: date,
    rng: random.Random, rng_np: np.random.Generator,
) -> list[dict]:
    """Emit a few discretionary transactions for the day."""
    # Discretionary spending stops in a deceased/dormant phase.
    if state["status"] != "active":
        return []
    # Average transactions per day = profile.monthly_tx_mean / 30
    base_per_day = profile.monthly_tx_mean / 30.0
    base_per_day *= state["activity_multiplier"]
    # Weekend slight bump
    if d.weekday() >= 5:
        base_per_day *= 1.25
    # Activity stochastic
    n = max(0, int(rng_np.poisson(base_per_day)))
    if n == 0:
        return []

    main = state["main"]
    lbl = state["labels"]
    cur, ctry = state["currency"], state["country"]
    pools = state["pools"]
    txs: list[dict] = []
    # Build category sampling weights for this day
    weights: dict[str, float] = {}
    for cat in DISCRETIONARY_CATEGORIES:
        base_w = BASELINE_CATEGORY_WEIGHTS[cat]
        bias = state["leisure_bias"].get(cat, 1.0)
        weights[cat] = base_w * bias * _seasonal_multiplier(d, cat) * _weekend_boost(d, cat)
    cats = list(weights.keys())
    wts = list(weights.values())

    # Adjust amount magnitude by the customer's *current-phase* income vs profile
    # baseline so spending tracks the trajectory (smaller baskets after a job loss).
    # The baseline is locale-scaled so the factor stays centred on ~1.0.
    baseline_income = max(1.0, profile.income_mean * state["income_scale"])
    income_factor = max(0.4, min(1.6, state["salary"] / baseline_income))

    for _ in range(n):
        cat = rng.choices(cats, weights=wts, k=1)[0]
        m = _pick_merchant(pools, cat, rng)
        amount = _amount_from_merchant(m, rng_np) * income_factor
        amount *= _inflation_factor(d, state["inflation_baseline"], state["inflation_table"])
        tx_type, channel = _channel_to_tx_type(m["channel"], rng)
        when = _random_time(d, cat, rng)
        new_bal, over, posted = _safe_post(main, amount)
        if not posted:
            continue  # Card payment declined at the POS / online checkout.
        city = customer.ville if channel != "online" else ""
        txs.append(_make_tx(
            main, when, amount, m["name"], m["mcc"], cat, m["subcategory"],
            tx_type, channel, label_for(m["name"], rng, state["locale"].label_noise), city=city,
            currency=cur, country=ctry, balance_after=new_bal,
        ))
        # If overdraft kicks in, charge agios on roughly 1-in-4 events to avoid spam.
        if over and rng.random() < 0.25:
            fee = round(rng.uniform(8, 25), 2)
            fee_bal, _, _ = _safe_post(main, -fee)
            txs.append(_make_tx(
                main, when + timedelta(minutes=5), -fee,
                lbl.overdraft_merchant(main.bank_name), "6012", "finance", "agios",
                "fee", "direct_debit", lbl.overdraft_label,
                currency=cur, country=ctry, balance_after=fee_bal,
            ))
    return txs


def _maybe_cash_withdrawal(state: dict, d: date, customer: Customer, rng: random.Random) -> list[dict]:
    if state["status"] != "active":
        return []
    # ~ once a week probability that scales lightly with profile
    p = 0.18 if state["active_profile"].name == "etudiant" else 0.14
    if rng.random() >= p:
        return []
    amount = float(rng.choice([20, 30, 40, 50, 60, 80, 100, 100, 150, 200]))
    when = _random_time(d, "transport", rng)
    lbl = state["labels"]
    new_bal, _, posted = _safe_post(state["main"], -amount)
    if not posted:
        return []
    return [_make_tx(
        state["main"], when, -amount, lbl.atm_merchant, "6011", "finance", "retrait_dab",
        "atm_withdrawal", "atm",
        lbl.atm_label(customer.ville),
        is_cash_withdrawal=True, city=customer.ville,
        currency=state["currency"], country=state["country"], balance_after=new_bal,
    )]


# Neutral preset for standalone / back-compat use (trajectory built inline).
_FALLBACK_PRESET = BankPresetSpec(preset_id="_fallback", distribution={},
                                  transition_propensity={})


def _emit_one_shot(
    state: dict, d: date, one_shot: tuple[str, float], transition: str, rng: random.Random,
) -> list[dict]:
    """Emit a transition's one-time expense (birth, marriage trip, home purchase…)."""
    cat, amount = one_shot
    lbl = state["labels"]
    when = _random_time(d, cat, rng)
    new_bal, _, posted = _safe_post(state["main"], -amount)
    if not posted:
        return []
    return [_make_tx(
        state["main"], when, -amount,
        lbl.oneshot_merchant(transition), "0000",
        cat if cat in state["pools"] or cat == "logement" else "divers",
        transition, "card_payment_online", "online",
        lbl.oneshot_label(transition),
        currency=state["currency"], country=state["country"], balance_after=new_bal,
    )]


def _advance_phase(state: dict, d: date, rng: random.Random) -> list[dict]:
    """Cross any life-phase boundaries reached by day `d`, re-binding behaviour."""
    txs: list[dict] = []
    phases = state["phases"]
    while state["phase_idx"] + 1 < len(phases) and phases[state["phase_idx"] + 1].start <= d:
        state["phase_idx"] += 1
        ph = phases[state["phase_idx"]]
        ap = PROFILES[ph.profile_name]
        state["active_profile"] = ap
        state["salary"] = ph.monthly_income
        state["rent"] = round(ph.monthly_income * ap.rent_ratio, 2) if ap.rent_ratio > 0 else 0.0
        state["leisure_bias"] = ph.leisure_bias
        state["activity_multiplier"] = ph.activity_multiplier
        state["status"] = ph.status
        state["freelance"] = ap.name in ("freelance", "entrepreneur")
        if ph.one_shot:
            txs += _emit_one_shot(state, d, ph.one_shot, ph.transition, rng)
    return txs


def effective_window_start(customer: Customer, accounts: list[Account], start: date) -> date:
    """Earliest day a customer can transact: clamped by bank entry & account opening."""
    main = next((a for a in accounts if a.role == AccountRole.CURRENT), accounts[0])
    return max(start, customer.date_entree_banque, main.date_ouverture)


def generate_transactions_for_customer(
    customer: Customer,
    accounts: list[Account],
    subs: list[Subscription],
    loans: list[Loan],
    start: date,
    end: date,
    seed: int,
    trajectory: Trajectory | None = None,
) -> Iterator[dict]:
    """Yield transactions for a single customer over [start, end]."""
    # A customer can only generate transactions from the date they joined the
    # bank, never before. Likewise the main account's date_ouverture acts as
    # a hard lower bound.
    effective_start = effective_window_start(customer, accounts, start)
    if effective_start > end:
        return
    rng = random.Random(seed)
    rng_np = np.random.default_rng(seed)
    locale = get_locale(customer.locale_code)
    if trajectory is None:
        # Back-compat: build the trajectory inline from the same per-customer seed.
        preset = BANK_PRESETS.get(customer.bank_preset) or _FALLBACK_PRESET
        trajectory = generate_trajectory(
            customer, effective_start, end, preset,
            random.Random(seed), np.random.default_rng(seed),
        )
    state = _state_for_customer(customer, accounts, subs, loans, trajectory.phases, rng_np, locale)
    salary_day = state["salary_day"]
    rent_day = state["rent_day"]
    # Walk day by day
    current = effective_start
    one_day = timedelta(days=1)
    while current <= end:
        # Cross life-phase boundaries (re-bind profile/income/status, emit one-shots)
        yield from _advance_phase(state, current, rng)
        active_profile = state["active_profile"]
        # Salary on salary_day (or freelance: irregular within last week of month)
        if state["freelance"]:
            # Spread invoices: do one batch around the 1st, 15th, end
            if current.day in (3, 14, 28) and rng.random() < 0.55:
                yield from _emit_salary(state, customer, active_profile, current, rng, rng_np)
        else:
            last_day = monthrange(current.year, current.month)[1]
            target = min(salary_day, last_day)
            if current.day == target:
                yield from _emit_salary(state, customer, active_profile, current, rng, rng_np)
        # Rent on rent_day
        if current.day == min(rent_day, monthrange(current.year, current.month)[1]):
            yield from _emit_rent(state, current, rng)
        # Subscriptions (standing orders — NOT status-gated)
        yield from _emit_subscriptions(state, current, rng)
        # Loans (standing orders — NOT status-gated)
        yield from _emit_loans(state, current, rng)
        # Daily discretionary spending
        yield from _emit_daily_spend(state, customer, active_profile, current, rng, rng_np)
        # Cash withdrawal occasionally
        yield from _maybe_cash_withdrawal(state, current, customer, rng)
        current += one_day


def generate_all_transactions(
    customers: list[Customer],
    accounts_by_customer: dict[str, list[Account]],
    subs_by_customer: dict[str, list[Subscription]],
    loans_by_customer: dict[str, list[Loan]],
    start: date,
    end: date,
    seed: int,
    trajectories_by_customer: dict[str, Trajectory] | None = None,
) -> Iterable[dict]:
    """Stream all transactions, customer by customer. Caller batches/writes."""
    trajectories_by_customer = trajectories_by_customer or {}
    for i, c in enumerate(customers):
        accs = accounts_by_customer.get(c.customer_id, [])
        if not accs:
            continue
        subs = subs_by_customer.get(c.customer_id, [])
        loans = loans_by_customer.get(c.customer_id, [])
        # Per-customer seed so a single customer is reproducible
        per_seed = (seed * 1_000_003 + i) & 0xFFFFFFFF
        yield from generate_transactions_for_customer(
            c, accs, subs, loans, start, end, per_seed,
            trajectories_by_customer.get(c.customer_id),
        )
