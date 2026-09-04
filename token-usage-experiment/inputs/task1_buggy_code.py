from collections import defaultdict


def group_transactions(transactions):
    """Group transactions by account_id and compute the running balance
    after each transaction, sorted by timestamp (oldest first).

    A transaction is a dict: {"account_id": str, "amount": float,
    "timestamp": int, "kind": "credit" | "debit"}.
    """
    grouped = defaultdict(list)
    for tx in transactions:
        grouped[tx["account_id"]].append(tx)

    result = {}
    for account_id, txs in grouped.items():
        txs.sort(key=lambda t: t["timestamp"], reverse=True)
        balance = 0
        history = []
        for tx in txs:
            if tx["kind"] == "credit":
                balance += tx["amount"]
            else:
                balance -= tx["amount"]
            history.append({"tx": tx, "balance_after": balance})
        result[account_id] = history

    return result


def average_daily_balance(history, start_day, end_day):
    """Given a per-account history (list from group_transactions),
    return the average balance across the [start_day, end_day) window.
    Timestamps in history are epoch seconds.
    """
    day_seconds = 86400
    if not history:
        return 0

    balances_by_day = {}
    for entry in history:
        day = entry["tx"]["timestamp"] // day_seconds
        balances_by_day[day] = entry["balance_after"]

    total = 0
    for day in range(start_day, end_day):
        total += balances_by_day.get(day, 0)
    return total / (end_day - start_day)


def top_accounts_by_activity(transactions, top_n=5):
    """Return the top-N account_ids by number of transactions."""
    counts = defaultdict(int)
    for tx in transactions:
        counts[tx["account_id"]] += 1
    return sorted(counts.items(), key=lambda kv: kv[1])[:top_n]
