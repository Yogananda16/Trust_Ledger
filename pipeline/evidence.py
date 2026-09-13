import json
from datetime import datetime
from pathlib import Path

DATA = Path("data")

TYPE_NAMES = {
    "ach_debit": "ACH",
    "wire_out": "wire",
    "international_wire_out": "international wire",
    "check_payment": "check",
}


def _load(filename):
    path = DATA / filename
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _dt(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _day(value):
    d = _dt(value)
    return f"{d:%b} {d.day}, {d.year}"


def _short_day(value):
    d = _dt(value)
    return f"{d:%b} {d.day}"


def _clock(value):
    return f"{_dt(value):%H:%M} UTC"


def _when(t):
    return t.get("posted_at") or t["initiated_at"]


def _amount(t):
    return abs(t["amount"]["amount"]) / 100


def _plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def _gap(seconds):
    if seconds < 3600:
        return _plural(max(1, round(seconds / 60)), "minute")
    if seconds < 86400:
        return _plural(round(seconds / 3600), "hour")
    return _plural(round(seconds / 86400), "day")


def build_evidence(flag, transactions):
    """Explain a flagged payment using the company's own records, one sentence per fact."""
    vendors = {v["name"]: v for v in _load("vendors.json")}
    approvals = {a["transaction_id"]: a for a in _load("approvals.json")}
    bank_changes = _load("bank_change_requests.json")
    by_id = {t["id"]: t for t in transactions}
    name = flag["counterparty_name"]
    payments = sorted(
        (t for t in transactions if t["counterparty_name"] == name and t["transaction_type"] in TYPE_NAMES),
        key=_when,
    )
    lines = []

    # A vendor paid soon after being added never had a track record.
    vendor = vendors.get(name)
    if vendor and payments:
        seconds = (_dt(payments[0]["initiated_at"]) - _dt(vendor["added_at"])).total_seconds()
        if 0 <= seconds <= 7 * 86400:
            lines.append(
                f"{name} was added to the vendor list by {vendor['added_by']} "
                f"{_gap(seconds)} before its first payment."
            )

    for signal in flag["signals"]:
        ctx = signal.get("context", {})

        if "new_account" in ctx:
            lines.append(
                f"{_plural(ctx['previous_count'], 'earlier payment')} to {name} went to account {ctx['old_account']}."
            )
            request = next(
                (r for r in bank_changes if r["vendor"] == name and r["new_account"] == ctx["new_account"]),
                None,
            )
            if request:
                lines.append(
                    f"On {_day(request['requested_at'])}, a request by {request['requested_via']} from "
                    f"{request['sender_email']} changed the account to {request['new_account']}."
                )
                sender_domain = request["sender_email"].split("@")[-1]
                on_file = (vendor or {}).get("email_domain")
                if on_file and sender_domain != on_file:
                    lines.append(
                        f"The sender's domain {sender_domain} doesn't match {on_file}, the domain on file for this vendor."
                    )
                if not request.get("callback_verified"):
                    lines.append("No call-back to a known phone number was recorded before the change.")
                seconds = (_dt(flag["initiated_at"]) - _dt(request["requested_at"])).total_seconds()
                lines.append(f"This payment was created {_gap(seconds)} after the change.")

        elif "known_vendor" in ctx:
            known = ctx["known_vendor"]
            mine, theirs = vendor or {}, vendors.get(known, {})
            if mine.get("email_domain") and theirs.get("email_domain"):
                lines.append(
                    f"{name} emails from {mine['email_domain']}, but {known}, already on file, uses {theirs['email_domain']}."
                )
            if mine.get("bank_account") and theirs.get("bank_account") and mine["bank_account"] != theirs["bank_account"]:
                lines.append(
                    f"It is paid to account {mine['bank_account']}, not {known}'s account {theirs['bank_account']}."
                )
            earlier = [t for t in transactions if t["counterparty_name"] == known and _when(t) < _when(flag)]
            if earlier:
                last = max(earlier, key=_when)
                lines.append(f"{known} was last paid ${_amount(last):,.2f} on {_day(_when(last))}.")

        elif "original_id" in ctx:
            original = by_id.get(ctx["original_id"])
            if original:
                lines.append(
                    f"Invoice {ctx['invoice']} was paid to {original['counterparty_name']} on "
                    f"{_day(_when(original))}: ${_amount(original):,.2f}, {original['status']}."
                )
                same = (
                    "same invoice number and amount"
                    if _amount(original) == flag["amount_dollars"]
                    else "same invoice number"
                )
                days = (_dt(_when(flag)) - _dt(_when(original))).days
                lines.append(
                    f"{_plural(days, 'day')} later, the {same} went to {name} by "
                    f"{TYPE_NAMES.get(flag['transaction_type'], 'payment')} ({flag['status']})."
                )

        elif "solicitation" in ctx:
            lines.append(
                f'The memo "{flag["clean_memo"]}" is a {ctx["solicitation"]} invoice, the format used by '
                f"unsolicited fake-invoice schemes that bill businesses for services they never ordered."
            )
            if len(payments) == 1:
                lines.append(f"There is no earlier payment or contract on record with {name}.")

        elif "average" in ctx:
            lines.append(
                f"This payment is ${flag['amount_dollars']:,.2f}; the {_plural(ctx['previous_count'], 'earlier payment')} "
                f"averaged ${ctx['average']:,.2f}."
            )

        elif "burst_ids" in ctx:
            members = sorted((by_id[i] for i in ctx["burst_ids"] if i in by_id), key=_when)
            listed = ", ".join(f"{m['counterparty_name']} (${_amount(m):,.0f})" for m in members)
            total = sum(_amount(m) for m in members)
            lines.append(
                f"On {_day(_when(members[0]))}, between {_clock(_when(members[0]))} and {_clock(_when(members[-1]))}, "
                f"payments to {len(members)} first-time payees were created: {listed}. Total ${total:,.0f}."
            )
            senders = sorted({m["user_full_name"] for m in members if m.get("user_full_name")})
            if senders:
                lines.append(f"Sent by {' and '.join(senders)}.")

        elif "payment_ids" in ctx:
            under = [by_id[i] for i in ctx["payment_ids"] if i in by_id]
            listed = ", ".join(f"${_amount(p):,.0f} on {_short_day(_when(p))}" for p in under)
            lines.append(
                f"{_plural(len(under), 'payment')} to {name} ({listed}) each stayed under the "
                f"${ctx['limit']:,} limit that needs a second approval."
            )

        elif "employee" in ctx:
            employee = ctx["employee"]
            already_said = any(line.startswith(f"{name} was added") for line in lines)
            if vendor and vendor["added_by"] == employee and not already_said:
                lines.append(f"{name} was added to the vendor list by {employee} on {_day(vendor['added_at'])}.")
            created = [p for p in payments if p.get("user_full_name") == employee]
            approved = [p for p in created if approvals.get(p["id"], {}).get("approved_by") == employee]
            if created:
                share = f"all {len(payments)}" if len(created) == len(payments) else f"{len(created)} of the {len(payments)}"
                sentence = f"{employee} created {share} payments to this vendor"
                if approved:
                    count = "all of them" if len(approved) == len(created) else _plural(len(approved), "of them")
                    sentence += f" and approved {count} with no second approver"
                lines.append(sentence + ".")

    approval = approvals.get(flag["id"])
    if approval:
        gap = _gap((_dt(approval["approved_at"]) - _dt(flag["initiated_at"])).total_seconds())
        if approval["approved_by"] == flag.get("user_full_name"):
            sentence = f"{approval['approved_by']} created this payment and approved it {gap} later"
        else:
            sentence = f"{approval['approved_by']} approved this payment {gap} after it was created"
        if approval["second_approval_required"] and not approval.get("second_approved_by"):
            sentence += ", without the required second approval"
        lines.append(sentence + ".")

    return list(dict.fromkeys(lines))
