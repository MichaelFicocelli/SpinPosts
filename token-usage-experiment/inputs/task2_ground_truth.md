# Task 2 — Ground truth for unit test coverage

Success criteria: proposed tests would exercise all of the following branches. Count of hit branches out of 8 determines score.

Branches / behaviors that must be covered:
1. `balance_cents <= 0` returns 0 (early exit).
2. Days-past-due within grace period (<= 10 weekday days) returns 0.
3. Days-past-due just past grace period returns a non-zero fee.
4. `MIN_FEE_CENTS` floor applies (small balance, few billable days, computed fee below $5.00).
5. `MAX_FEE_FRACTION` cap applies (large days-past-due drives raw fee above 25% of balance).
6. Weekend days do NOT count toward `days_past_due` (e.g., due Friday, today Monday → 1 weekday day).
7. Rounding half-up on fractional cents (result depends on `int(raw_fee + 0.5)`).
8. Custom `today` parameter (dependency injection) works — deterministic tests without patching `date.today`.

Scoring:
- 7-8 branches: success
- 4-6 branches: partial
- 0-3 branches: fail
