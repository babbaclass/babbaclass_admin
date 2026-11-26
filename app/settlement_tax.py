"""정산 세금 계산 — 경영지원부 기준 십 단위 절사(ROUNDDOWN, -1)."""
from __future__ import annotations

import math


def round_down_to_tens(amount: float | int) -> int:
    """Excel ROUNDDOWN(value, -1)와 동일: 10원 단위 절사."""
    if amount <= 0:
        return 0
    return int(math.floor(float(amount) / 10) * 10)


def calc_settlement_taxes(income: int | float) -> tuple[int, int, int]:
    """
    정산서 세금 공제 계산.
    - 사업소득세: ROUNDDOWN(income * 0.03, -1)
    - 지방세: ROUNDDOWN(사업소득세 * 0.1, -1)
    """
    income = int(income or 0)
    deducted_tax = round_down_to_tens(income * 0.03)
    deducted_local_tax = round_down_to_tens(deducted_tax * 0.10)
    net_amount = income - deducted_tax - deducted_local_tax
    return deducted_tax, deducted_local_tax, net_amount
