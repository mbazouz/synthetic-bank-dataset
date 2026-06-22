"""Cards: 1-2 cards per compte courant / compte joint / compte pro."""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from datetime import date, timedelta

from .accounts import Account
from .banking_utils import generate_card_number, mask_card_number
from .customers import Customer
from .locales import AccountRole


CARD_TYPES = {
    "etudiant":     [("Visa Electron", "debit", 0.9), ("Visa Classic", "debit", 0.1)],
    "jeune_actif":  [("Visa Classic", "debit", 0.55), ("Mastercard Standard", "debit", 0.3), ("Visa Premier", "debit", 0.15)],
    "famille":      [("Visa Premier", "debit", 0.55), ("Mastercard Gold", "debit", 0.35), ("Visa Classic", "debit", 0.10)],
    "cadre":        [("Visa Premier", "debit", 0.5), ("Mastercard Gold", "debit", 0.4), ("Mastercard Platinum", "credit", 0.10)],
    "csp_plus":     [("Visa Platinum", "debit", 0.5), ("Mastercard Platinum", "credit", 0.3), ("Visa Infinite", "credit", 0.2)],
    "freelance":    [("Visa Business", "debit", 0.55), ("Mastercard Business", "debit", 0.45)],
    "entrepreneur": [("Visa Business", "debit", 0.5), ("Mastercard Business", "debit", 0.4), ("Visa Platinum Business", "credit", 0.10)],
    "investisseur": [("Visa Infinite", "credit", 0.4), ("Visa Premier", "debit", 0.4), ("Mastercard Platinum", "credit", 0.2)],
    "retraite":     [("Visa Classic", "debit", 0.5), ("Mastercard Standard", "debit", 0.3), ("Visa Premier", "debit", 0.2)],
    "fragile":      [("Visa Electron", "debit", 0.85), ("Visa Classic", "debit", 0.15)],
}


@dataclass
class Card:
    card_id: str
    account_id: str
    customer_id: str
    card_number_masked: str
    scheme: str
    type: str  # debit / credit
    product: str  # commercial name
    date_emission: date
    date_expiration: date
    statut: str
    plafond_paiement_mensuel: float
    plafond_retrait_mensuel: float
    contactless: bool

    def to_row(self) -> dict:
        return {
            "card_id": self.card_id,
            "account_id": self.account_id,
            "customer_id": self.customer_id,
            "card_number_masked": self.card_number_masked,
            "scheme": self.scheme,
            "type": self.type,
            "product": self.product,
            "issued_at": self.date_emission.isoformat(),
            "expires_at": self.date_expiration.isoformat(),
            "status": self.statut,
            "monthly_payment_limit": self.plafond_paiement_mensuel,
            "monthly_withdrawal_limit": self.plafond_retrait_mensuel,
            "contactless": self.contactless,
        }


def _scheme_from_product(product: str) -> str:
    return "mastercard" if "Mastercard" in product else "visa"


def generate_cards(customers_by_id: dict[str, Customer], accounts: list[Account], seed: int) -> list[Card]:
    rng = random.Random(seed)
    cards: list[Card] = []
    next_id = 1
    for acc in accounts:
        if acc.role not in (AccountRole.CURRENT, AccountRole.JOINT, AccountRole.BUSINESS):
            continue
        customer = customers_by_id[acc.customer_id]
        options = CARD_TYPES[customer.profil]
        products = [o[0] for o in options]
        types = [o[1] for o in options]
        weights = [o[2] for o in options]

        n_cards = 1 if rng.random() < 0.7 else 2
        for k in range(n_cards):
            idx = rng.choices(range(len(options)), weights=weights, k=1)[0]
            product = products[idx]
            ctype = types[idx]
            scheme = _scheme_from_product(product)
            issue = acc.date_ouverture + timedelta(days=rng.randint(0, 60))
            issue = min(issue, date.today() - timedelta(days=1))
            expire = issue + timedelta(days=365 * rng.choice([3, 4, 5]))
            pan = generate_card_number(rng, scheme)
            # Limits scale with profile / product
            base_paiement = {
                "Visa Electron": 1000, "Visa Classic": 2500, "Mastercard Standard": 2500,
                "Visa Premier": 5000, "Mastercard Gold": 5000,
                "Visa Platinum": 9000, "Mastercard Platinum": 9000,
                "Visa Infinite": 15000,
                "Visa Business": 6000, "Mastercard Business": 6000, "Visa Platinum Business": 12000,
            }.get(product, 3000)
            base_retrait = base_paiement * 0.3
            cards.append(Card(
                card_id=f"K{next_id:08d}",
                account_id=acc.account_id,
                customer_id=acc.customer_id,
                card_number_masked=mask_card_number(pan),
                scheme=scheme,
                type=ctype,
                product=product,
                date_emission=issue,
                date_expiration=expire,
                statut="active",
                plafond_paiement_mensuel=float(base_paiement),
                plafond_retrait_mensuel=float(round(base_retrait, 2)),
                contactless=product != "Visa Electron",
            ))
            next_id += 1
    return cards
