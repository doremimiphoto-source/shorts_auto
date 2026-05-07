"""Kill-Switch 자동 평가 (§12).

플래그 파일 기반 수동 킬은 utils/lock.py 참고.
본 모듈은 DB 지표를 읽어 자동으로 플래그를 생성한다.

평가 항목 (config.yaml killswitch 섹션):
  upload_failure_rate_2d       - 2일 연속 업로드 실패율 > 임계값
  cumulative_similarity_threshold - 최근 30일 평균 유사도 > 임계값
  (ctr_7d / retention_7d — YouTube Analytics 연동 시 추가 예정)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EvalResult:
    triggered: bool
    reasons: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.triggered


class KillSwitchEvaluator:
    def __init__(self, flag_path: str | Path, *, config: dict) -> None:
        self.flag_path = Path(flag_path)
        self._cfg = config

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def evaluate(self, repos) -> EvalResult:
        """지표를 검사하고 필요 시 플래그 파일을 생성한다."""
        reasons: list[str] = []

        reasons += self._check_upload_failure_rate(repos)
        reasons += self._check_cumulative_similarity(repos)

        if reasons:
            self._arm(reasons)
            return EvalResult(triggered=True, reasons=reasons)
        return EvalResult(triggered=False)

    def arm(self, reason: str) -> None:
        """외부(정책 경고 등)에서 직접 킬스위치를 활성화한다."""
        self._arm([reason])

    # ------------------------------------------------------------------
    # Internal checks
    # ------------------------------------------------------------------

    def _check_upload_failure_rate(self, repos) -> list[str]:
        threshold = float(self._cfg.get("upload_failure_rate_2d", 0.50))
        row = repos.db.fetchone(
            """
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed
            FROM uploads
            WHERE DATE(uploaded_at) >= DATE('now', '-2 days', 'localtime')
            """
        )
        if not row or not row["total"]:
            return []
        rate = row["failed"] / row["total"]
        if rate > threshold:
            return [f"upload_failure_rate_2d={rate:.2%} > threshold={threshold:.0%}"]
        return []

    def _check_cumulative_similarity(self, repos) -> list[str]:
        threshold = float(self._cfg.get("cumulative_similarity_threshold", 0.6))
        row = repos.db.fetchone(
            """
            SELECT AVG(similarity_30d) AS avg_sim
            FROM scripts
            WHERE created_at >= DATE('now', '-30 days', 'localtime')
              AND similarity_30d IS NOT NULL
            """
        )
        if not row or row["avg_sim"] is None:
            return []
        avg = float(row["avg_sim"])
        if avg >= threshold:
            return [f"cumulative_similarity_30d={avg:.3f} >= threshold={threshold}"]
        return []

    # ------------------------------------------------------------------
    # Flag file
    # ------------------------------------------------------------------

    def _arm(self, reasons: list[str]) -> None:
        self.flag_path.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(reasons)
        self.flag_path.write_text(body, encoding="utf-8")
