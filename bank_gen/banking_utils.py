"""IBAN / BIC / SIREN synthetic helpers (FR format, valid mod-97 check)."""
from __future__ import annotations

import random
import string


def _mod97(s: str) -> int:
    """Stream-friendly mod-97 (RFC 13616)."""
    rem = 0
    for ch in s:
        rem = (rem * 10 + int(ch)) % 97
    return rem


def _letters_to_digits(s: str) -> str:
    out = []
    for c in s:
        if c.isdigit():
            out.append(c)
        else:
            out.append(str(ord(c.upper()) - 55))  # A=10, B=11, ...
    return "".join(out)


def generate_iban_fr(rng: random.Random, bank_code: str) -> str:
    """Build a syntactically valid FR IBAN (mod-97 check).

    BBAN (FR) = 5-digit bank code + 5-digit branch + 11-char account + 2-digit RIB key.
    We compute both the RIB key and the IBAN check digits properly.
    """
    branch = f"{rng.randint(0, 99999):05d}"
    account_chars = string.ascii_uppercase + string.digits
    account = "".join(rng.choice(account_chars) for _ in range(11))
    # RIB key: compute 97 - mod97(bank+branch+account_as_digits + "00") then format on 2 digits.
    bban_no_key = bank_code + branch + account
    rib_key = 97 - _mod97(_letters_to_digits(bban_no_key) + "00")
    bban = f"{bban_no_key}{rib_key:02d}"
    # IBAN check digits: 98 - mod97( bban_as_digits + "FR00" )
    check = 98 - _mod97(_letters_to_digits(bban) + _letters_to_digits("FR") + "00")
    return f"FR{check:02d}{bban}"


def generate_iban_gb(rng: random.Random, bank_alpha4: str) -> str:
    """Build a syntactically valid GB IBAN (mod-97 check).

    BBAN (GB) = 4-letter bank code + 6-digit sort code + 8-digit account number.
    """
    bank = (bank_alpha4 + "ZZZZ")[:4].upper()
    sort = f"{rng.randint(0, 999999):06d}"
    account = f"{rng.randint(0, 99999999):08d}"
    bban = bank + sort + account
    check = 98 - _mod97(_letters_to_digits(bban) + _letters_to_digits("GB") + "00")
    return f"GB{check:02d}{bban}"


def _aba_routing(rng: random.Random) -> str:
    """Build a 9-digit US ABA routing number with a valid check digit."""
    d = [rng.randint(0, 9) for _ in range(8)]
    # 3*(d1+d4+d7) + 7*(d2+d5+d8) + (d3+d6+d9) ≡ 0 (mod 10); solve for d9 (index 8).
    partial = (3 * (d[0] + d[3] + d[6]) + 7 * (d[1] + d[4] + d[7]) + (d[2] + d[5])) % 10
    check = (10 - partial) % 10
    return "".join(str(x) for x in d) + str(check)


def generate_account_number_us(rng: random.Random, bank_code: str) -> str:
    """US accounts have no IBAN: return 'ROUTING ACCOUNT' (ABA routing + account no.)."""
    routing = bank_code if (bank_code and bank_code.isdigit() and len(bank_code) == 9) else _aba_routing(rng)
    account = "".join(str(rng.randint(0, 9)) for _ in range(rng.choice([8, 9, 10, 11, 12])))
    return f"{routing} {account}"


def generate_card_number(rng: random.Random, scheme: str = "visa") -> str:
    """Build a Luhn-valid 16-digit PAN."""
    if scheme == "visa":
        prefix = "4"
    elif scheme == "mastercard":
        prefix = str(rng.choice([51, 52, 53, 54, 55]))
    else:
        prefix = "5"
    body = prefix + "".join(str(rng.randint(0, 9)) for _ in range(15 - len(prefix)))
    # Luhn check digit
    total = 0
    for i, d in enumerate(reversed(body)):
        n = int(d)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    check = (10 - total % 10) % 10
    return body + str(check)


def mask_card_number(pan: str) -> str:
    return f"{pan[:4]} **** **** {pan[-4:]}"


def generate_siren(rng: random.Random) -> str:
    """Build a Luhn-valid 9-digit SIREN."""
    body = "".join(str(rng.randint(0, 9)) for _ in range(8))
    total = 0
    for i, d in enumerate(reversed(body)):
        n = int(d)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    check = (10 - total % 10) % 10
    return body + str(check)
