# Task 1 — Ground truth bugs

There are 3 bugs in the snippet. A "success" identifies all 3; "partial" identifies 1-2; "fail" identifies 0 or invents non-bugs.

1. **`group_transactions`**: `txs.sort(..., reverse=True)` sorts newest first, but the docstring says oldest first. Fix: remove `reverse=True`. This also cascades into wrong balances since credits/debits are applied in the wrong order.
2. **`average_daily_balance`**: Days without a transaction default to balance 0 via `balances_by_day.get(day, 0)`, but the balance should carry forward from the last known day. Fix: sort history by day and forward-fill the balance across the window.
3. **`top_accounts_by_activity`**: `sorted(..., key=lambda kv: kv[1])` returns ascending order (bottom-N), missing `reverse=True`. Fix: add `reverse=True`.
