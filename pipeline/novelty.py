from collections import defaultdict

OUTGOING_TYPES = {"card_debit", "ach_debit", "wire_debit"}


def flag_novel_vendors(transactions):
    outgoing = [t for t in transactions if t["transaction_type"] in OUTGOING_TYPES]
    outgoing.sort(key=lambda t: t.get("posted_at") or t.get("initiated_at") or "")
    history = defaultdict(list)
    flagged = []

    for t in outgoing:
        name = t["counterparty_name"]
        amount = abs(t["amount"]["amount"]) / 100
        past = history[name]

        is_novel = len(past) == 0
        is_outlier = bool(past) and amount > (sum(past) / len(past)) * 2

        if is_novel or is_outlier:
            reason = (
                "first payment to this vendor"
                if is_novel
                else f"${amount:.2f} is over 2x this vendor's average (${sum(past)/len(past):.2f})"
            )
            flagged.append(
                {
                    **t,
                    "amount_dollars": amount,
                    "is_novel": is_novel,
                    "is_outlier": is_outlier,
                    "reason": reason,
                }
            )

        history[name].append(amount)

    return flagged
