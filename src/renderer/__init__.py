"""영상 합성 (FR-5).

FFmpeg `-filter_complex` 직접 호출. MoviePy는 보조 (스크립트 생성용).
"""

from .composer import VideoComposer
from .assets import AssetSelector

__all__ = ["VideoComposer", "AssetSelector"]
