"""Settlement aggregation helpers shared by overview/status/statement views."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, List, Sequence, TypeVar

from app.models import Settlement

T = TypeVar("T", bound=Settlement)


def select_canonical_settlements(settlements: Sequence[T] | Iterable[T]) -> List[T]:
    """
    집계용 Settlement 선택.

    같은 사용자·연·월에 mtd/daily 스냅샷과 monthly가 섞여 있으면
    monthly를 우선하고, monthly가 없으면 최신 스냅샷 1건만 남긴다.
    """
    groups: dict[tuple[int, int, int], list[T]] = defaultdict(list)
    for settlement in settlements:
        if not settlement or not settlement.settlement_date:
            continue
        key = (
            int(settlement.user_id),
            int(settlement.settlement_date.year),
            int(settlement.settlement_date.month),
        )
        groups[key].append(settlement)

    selected: List[T] = []
    for rows in groups.values():
        monthly_rows = [row for row in rows if row.settlement_type == "monthly"]
        if monthly_rows:
            selected.append(max(monthly_rows, key=lambda row: int(row.settlement_id or 0)))
            continue
        selected.append(
            max(
                rows,
                key=lambda row: (
                    row.settlement_date,
                    int(row.settlement_id or 0),
                ),
            )
        )
    return selected
