import math
import re
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher

# Vendor bill payments — where the fraud research says impersonation happens.
# Card swipes (card_debit) are employee purchases, not vendor invoicing,
# so they're deliberately excluded.
OUTGOING_TYPES = {"ach_debit", "wire_out", "international_wire_out", "check_payment"}
WIRE_TYPES = {"wire_out", "international_wire_out"}

# Below this, a first-time vendor isn't worth a founder's attention.
MIN_AMOUNT = 500

# Wires this large are hard to claw back once sent.
LARGE_WIRE = 10_000

# Payments at or above this need a second approval (assumed company policy).
APPROVAL_LIMIT = 5_000

# New payees paid this close together look like a pressured payment run.
BURST_WINDOW_MINUTES = 60

# Name similarity above this, to a vendor already paid, looks like impersonation.
LOOKALIKE_RATIO = 0.85

# Memos that say nothing about what was actually bought.
VAGUE_MEMOS = {"", "payment", "transfer", "wire", "vendor payment", "transfer to external account"}

INVOICE_REF = re.compile(r"\binvoice\s*#?\s*(\d[\w-]*)", re.IGNORECASE)
PRESSURE_WORDS = re.compile(
    r"\b(urgent|confidential|asap|immediately|wire today|per (?:ceo|cfo))\b", re.IGNORECASE
)


def _clean_memo(memo):
    # Drop bank error prefixes like "[INVALID_RECEIVING_ROUTING_NUMBER] ".
    memo = re.sub(r"^\[[^\]]*\]\s*", "", memo or "").strip()
    # International wires repeat the memo as "note: X, reason: Y, ref: Z".
    note = re.match(r"note:\s*(.*?),\s*reason:", memo)
    return note.group(1).strip() if note else memo


def _time(t):
    return datetime.fromisoformat((t.get("posted_at") or t["initiated_at"]).replace("Z", "+00:00"))


def _signal(label, pattern=None, hidden=False, **context):
    # context carries what the evidence builder needs to explain the signal.
    # hidden signals still drive patterns and evidence but aren't shown as chips.
    return {"label": label, "pattern": pattern, "hidden": hidden, "context": context}


def flag_novel_vendors(transactions):
    employees = {t["user_full_name"] for t in transactions if t.get("user_full_name")}
    outgoing = [t for t in transactions if t["transaction_type"] in OUTGOING_TYPES]
    outgoing.sort(key=lambda t: t.get("posted_at") or t.get("initiated_at") or "")

    history = defaultdict(list)
    accounts = defaultdict(list)
    under_limit = defaultdict(list)
    invoice_first = {}
    flagged = []

    for t in outgoing:
        name = t["counterparty_name"]
        amount = abs(t["amount"]["amount"]) / 100
        past = history[name]
        memo = _clean_memo(t.get("memo"))
        account = t.get("counterparty_account")
        signals = []

        is_novel = len(past) == 0 and amount >= MIN_AMOUNT
        is_outlier = (
            bool(past) and amount > (sum(past) / len(past)) * 2 and amount >= MIN_AMOUNT
        )

        if is_novel:
            signals.append(_signal("first payment to this vendor"))
        if is_outlier:
            signals.append(_signal(
                f"${amount:.2f} is over 2x this vendor's average (${sum(past)/len(past):.2f})",
                "fake_invoice",
                average=sum(past) / len(past),
                previous_count=len(past),
            ))

        if account and accounts[name] and account != accounts[name][-1]:
            signals.append(_signal(
                f"Bank details changed ({accounts[name][-1]} → {account})",
                "bank_change",
                old_account=accounts[name][-1],
                new_account=account,
                previous_count=accounts[name].count(accounts[name][-1]),
            ))

        if not past:
            for known in history:
                if known != name and SequenceMatcher(None, name.lower(), known.lower()).ratio() >= LOOKALIKE_RATIO:
                    signals.append(_signal(f"Name looks like {known}", "lookalike", known_vendor=known))
                    break

        invoice = INVOICE_REF.search(memo)
        if invoice:
            ref = invoice.group(1)
            first = invoice_first.setdefault(ref, t)
            if first["counterparty_name"] != name:
                signals.append(_signal(
                    f"Invoice {ref} already used by {first['counterparty_name']}",
                    "fake_invoice",
                    invoice=ref,
                    original_id=first["id"],
                ))

        if t["transaction_type"] in WIRE_TYPES and amount >= LARGE_WIRE:
            signals.append(_signal(f"${amount:,.0f} wire"))

        if amount >= MIN_AMOUNT and memo.lower() in VAGUE_MEMOS:
            signals.append(_signal(f'vague memo: "{memo}"' if memo else "no memo"))

        pressure = PRESSURE_WORDS.search(memo)
        if pressure:
            signals.append(_signal(
                f'Pressure language: "{pressure.group(0).lower()}"', "exec_pressure", hidden=True
            ))

        if APPROVAL_LIMIT * 0.9 <= amount < APPROVAL_LIMIT:
            under_limit[name].append(t["id"])
            if len(under_limit[name]) >= 2:
                signals.append(_signal(
                    f"{len(under_limit[name])} payments just under the ${APPROVAL_LIMIT:,} approval limit",
                    "insider",
                    payment_ids=list(under_limit[name]),
                    limit=APPROVAL_LIMIT,
                ))

        for employee in employees:
            surname = employee.split()[-1]
            if name != employee and len(surname) >= 4 and re.search(rf"\b{re.escape(surname)}\b", name, re.IGNORECASE):
                sent_by = ", who sent it" if t.get("user_full_name") == employee else ""
                signals.append(_signal(
                    f"Payee shares a name with employee {employee}{sent_by}", "insider", employee=employee
                ))
                break

        if amount >= MIN_AMOUNT and t["status"] == "awaiting_approval":
            signals.append(_signal("awaiting approval, can still be stopped"))

        if signals:
            flagged.append(
                {
                    **t,
                    "amount_dollars": amount,
                    "clean_memo": memo,
                    "is_novel": is_novel,
                    "is_outlier": is_outlier,
                    "signals": signals,
                }
            )

        history[name].append(amount)
        if account:
            accounts[name].append(account)

    # Several new payees paid within a short window, e.g. a pressured "confidential" payment run.
    novel = [f for f in flagged if f["is_novel"]]
    for f in novel:
        burst = [g for g in novel if abs((_time(g) - _time(f)).total_seconds()) <= BURST_WINDOW_MINUTES * 60]
        if len(burst) >= 2:
            times = [_time(g) for g in burst]
            span = max(1, math.ceil((max(times) - min(times)).total_seconds() / 60))
            f["signals"].append(_signal(
                f"{len(burst)} new payees paid within {span} min",
                "exec_pressure",
                hidden=True,
                burst_ids=[g["id"] for g in burst],
            ))

    for f in flagged:
        f["reason"] = "; ".join(s["label"] for s in f["signals"])

    return flagged
