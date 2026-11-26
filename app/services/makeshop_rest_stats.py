"""
MakeShop REST 호출 집계 (sync 구간용).

성공은 Chat을 보내지 않고 카운트만 쌓고, sync 종료 요약에 포함한다.
실패는 즉시 Chat + 요약에도 포함한다.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional

_MAX_FAILURE_SAMPLES = 8

_current_collector: ContextVar[Optional["RestCallStatsCollector"]] = ContextVar(
    "makeshop_rest_stats_collector",
    default=None,
)


@dataclass
class RestCallFailure:
    method: str
    path: str
    status_code: Optional[int] = None
    code: Optional[str] = None
    detail: Optional[str] = None

    def short_line(self) -> str:
        parts = [f"{self.method.upper()} {self.path}"]
        if self.status_code is not None:
            parts.append(f"HTTP {self.status_code}")
        if self.code:
            parts.append(str(self.code))
        if self.detail:
            parts.append(str(self.detail)[:120])
        return " → ".join(parts[:1] + [", ".join(parts[1:])] if len(parts) > 1 else parts)


@dataclass
class RestCallStatsCollector:
    success_count: int = 0
    failure_count: int = 0
    by_key: Dict[str, Dict[str, int]] = field(default_factory=dict)
    failures: List[RestCallFailure] = field(default_factory=list)

    def record(
        self,
        *,
        success: bool,
        method: str,
        path: str,
        status_code: Optional[int] = None,
        code: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        key = f"{method.upper()} {path}"
        bucket = self.by_key.setdefault(key, {"ok": 0, "fail": 0})
        if success:
            self.success_count += 1
            bucket["ok"] += 1
            return
        self.failure_count += 1
        bucket["fail"] += 1
        if len(self.failures) < _MAX_FAILURE_SAMPLES:
            self.failures.append(
                RestCallFailure(
                    method=method,
                    path=path,
                    status_code=status_code,
                    code=code,
                    detail=detail,
                )
            )

    def snapshot(self) -> Dict[str, Any]:
        return {
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "total_count": self.success_count + self.failure_count,
            "by_key": dict(self.by_key),
            "failures": [
                {
                    "method": f.method,
                    "path": f.path,
                    "status_code": f.status_code,
                    "code": f.code,
                    "detail": f.detail,
                    "line": f.short_line(),
                }
                for f in self.failures
            ],
            "failures_truncated": self.failure_count > len(self.failures),
        }


def get_rest_call_stats_collector() -> Optional[RestCallStatsCollector]:
    return _current_collector.get()


def record_rest_call(
    *,
    success: bool,
    method: str,
    path: str,
    status_code: Optional[int] = None,
    code: Optional[str] = None,
    detail: Optional[str] = None,
) -> None:
    collector = get_rest_call_stats_collector()
    if collector is None:
        return
    collector.record(
        success=success,
        method=method,
        path=path,
        status_code=status_code,
        code=code,
        detail=detail,
    )


@contextmanager
def rest_call_stats_scope() -> Iterator[RestCallStatsCollector]:
    collector = RestCallStatsCollector()
    token = _current_collector.set(collector)
    try:
        yield collector
    finally:
        _current_collector.reset(token)


def format_rest_stats_chat_lines(stats: Optional[Dict[str, Any]]) -> List[str]:
    if not stats:
        return []
    ok = int(stats.get("success_count") or 0)
    fail = int(stats.get("failure_count") or 0)
    total = int(stats.get("total_count") or (ok + fail))
    lines = [f"• REST: 성공 {ok} / 실패 {fail} (총 {total})"]
    by_key = stats.get("by_key") or {}
    if by_key:
        # 호출이 많은 순으로 최대 6개
        ranked = sorted(
            by_key.items(),
            key=lambda item: -(item[1].get("ok", 0) + item[1].get("fail", 0)),
        )
        parts = []
        for key, counts in ranked[:6]:
            parts.append(f"{key} ok={counts.get('ok', 0)} fail={counts.get('fail', 0)}")
        if parts:
            lines.append(f"• REST 내역: {'; '.join(parts)}")
        if len(ranked) > 6:
            lines.append(f"• REST 내역: …외 {len(ranked) - 6}종")
    failures = stats.get("failures") or []
    for item in failures[:5]:
        line = item.get("line") if isinstance(item, dict) else None
        if line:
            lines.append(f"• 실패: {line}")
    if stats.get("failures_truncated"):
        lines.append(f"• 실패: …외 {fail - len(failures)}건")
    return lines
