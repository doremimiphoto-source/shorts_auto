"""src.utils.killswitch 단위 테스트."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.utils.killswitch import EvalResult, KillSwitchEvaluator


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _make_repos(*, total: int, failed: int, avg_sim: float | None = None):
    """DB fetchone 결과를 흉내내는 mock repos."""
    repos = MagicMock()
    call_count = [0]

    def _fetchone(sql, *args, **kwargs):
        call_count[0] += 1
        if "uploads" in sql:
            if total == 0:
                return None
            return {"total": total, "failed": failed}
        if "scripts" in sql:
            if avg_sim is None:
                return {"avg_sim": None}
            return {"avg_sim": avg_sim}
        return None

    repos.db.fetchone.side_effect = _fetchone
    return repos


# ---------------------------------------------------------------------------
# 기본 동작
# ---------------------------------------------------------------------------

def test_no_trigger_when_no_uploads(tmp_path: Path) -> None:
    flag = tmp_path / "ks.flag"
    ev = KillSwitchEvaluator(flag, config={"upload_failure_rate_2d": 0.50})
    result = ev.evaluate(_make_repos(total=0, failed=0))
    assert not result.triggered
    assert not flag.exists()


def test_no_trigger_below_failure_threshold(tmp_path: Path) -> None:
    flag = tmp_path / "ks.flag"
    ev = KillSwitchEvaluator(flag, config={"upload_failure_rate_2d": 0.50})
    result = ev.evaluate(_make_repos(total=4, failed=1))  # 25% < 50%
    assert not result.triggered
    assert not flag.exists()


def test_trigger_on_high_failure_rate(tmp_path: Path) -> None:
    flag = tmp_path / "ks.flag"
    ev = KillSwitchEvaluator(flag, config={"upload_failure_rate_2d": 0.50})
    result = ev.evaluate(_make_repos(total=4, failed=3))  # 75% > 50%
    assert result.triggered
    assert flag.exists()
    assert "upload_failure_rate_2d" in result.reasons[0]


def test_trigger_exact_boundary_is_not_triggered(tmp_path: Path) -> None:
    flag = tmp_path / "ks.flag"
    ev = KillSwitchEvaluator(flag, config={"upload_failure_rate_2d": 0.50})
    result = ev.evaluate(_make_repos(total=2, failed=1))  # 50% == 50% → NOT triggered (strict >)
    assert not result.triggered


def test_trigger_on_high_similarity(tmp_path: Path) -> None:
    flag = tmp_path / "ks.flag"
    cfg = {"upload_failure_rate_2d": 0.50, "cumulative_similarity_threshold": 0.6}
    result = KillSwitchEvaluator(flag, config=cfg).evaluate(
        _make_repos(total=0, failed=0, avg_sim=0.65)
    )
    assert result.triggered
    assert flag.exists()
    assert "cumulative_similarity" in result.reasons[0]


def test_no_trigger_below_similarity_threshold(tmp_path: Path) -> None:
    flag = tmp_path / "ks.flag"
    cfg = {"upload_failure_rate_2d": 0.50, "cumulative_similarity_threshold": 0.6}
    result = KillSwitchEvaluator(flag, config=cfg).evaluate(
        _make_repos(total=0, failed=0, avg_sim=0.45)
    )
    assert not result.triggered


def test_multiple_reasons_accumulated(tmp_path: Path) -> None:
    flag = tmp_path / "ks.flag"
    cfg = {"upload_failure_rate_2d": 0.50, "cumulative_similarity_threshold": 0.6}
    result = KillSwitchEvaluator(flag, config=cfg).evaluate(
        _make_repos(total=2, failed=2, avg_sim=0.70)
    )
    assert result.triggered
    assert len(result.reasons) == 2


def test_arm_directly(tmp_path: Path) -> None:
    flag = tmp_path / "ks.flag"
    ev = KillSwitchEvaluator(flag, config={})
    ev.arm("policy_warning: 1 strike")
    assert flag.exists()
    assert "policy_warning" in flag.read_text(encoding="utf-8")


def test_flag_file_content_contains_reason(tmp_path: Path) -> None:
    flag = tmp_path / "ks.flag"
    ev = KillSwitchEvaluator(flag, config={"upload_failure_rate_2d": 0.50})
    ev.evaluate(_make_repos(total=4, failed=3))
    content = flag.read_text(encoding="utf-8")
    assert "upload_failure_rate_2d" in content


# ---------------------------------------------------------------------------
# EvalResult bool 동작
# ---------------------------------------------------------------------------

def test_evalresult_bool_false():
    assert not EvalResult(triggered=False)


def test_evalresult_bool_true():
    assert EvalResult(triggered=True, reasons=["x"])
