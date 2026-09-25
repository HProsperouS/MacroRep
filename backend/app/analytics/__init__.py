"""Deterministic fitness calculations shared by every domain.

Pure functions only: plain numbers and dates in, plain numbers out — no
database access, no ORM models, no request context — so each formula can be
unit-tested against known values and reused unchanged by the services, the
progress dashboard, and the coach's analysis tools. The formulas and why they
were chosen are documented in ``docs/analytics.md``.
"""
