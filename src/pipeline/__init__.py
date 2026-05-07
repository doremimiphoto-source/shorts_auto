"""파이프라인 단계별 함수.

각 단계는 PipelineContext를 받아 DB의 단일 레코드 ID를 반환한다.
단계 간 입력은 ID로 전달되며, 실제 데이터는 Repository를 통해 조회한다.
"""

from .context import PipelineContext, StageError, StageSkipped
from .crawl_stage import run as run_crawl
from .rewrite_stage import run as run_rewrite

__all__ = [
    "PipelineContext",
    "StageError",
    "StageSkipped",
    "run_crawl",
    "run_rewrite",
]
