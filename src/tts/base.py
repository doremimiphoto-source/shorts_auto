"""TTS 엔진 추상 인터페이스 (FR-3)."""

from __future__ import annotations

import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


def _resolve_ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    winget = Path.home() / "AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe"
    if winget.exists():
        return str(winget)
    return "ffmpeg"


@dataclass
class SynthResult:
    audio_path: Path
    duration_seconds: float
    sample_rate: int
    speaker_id: str
    engine: str
    lufs: float | None = None
    metadata: dict = field(default_factory=dict)
    # metadata["segment_times"] = {"hook": {"start": 0.0, "end": 3.2}, "body": {...}, "twist": {...}}


def _concat_audio_with_gaps(
    audio_files: list[Path],
    gap_seconds: list[float],
    out_path: Path,
    sample_rate: int = 24000,
) -> None:
    """ffmpeg concat filter로 오디오 파일 사이에 묵음 갭을 삽입해 연결."""
    cmd = [_resolve_ffmpeg(), "-hide_banner", "-y"]
    filter_parts: list[str] = []
    stream_idx = 0

    for i, f in enumerate(audio_files):
        cmd += ["-i", str(f)]
        filter_parts.append(f"[{stream_idx}:a]")
        stream_idx += 1
        if i < len(gap_seconds) and gap_seconds[i] > 0:
            cmd += [
                "-f", "lavfi", "-i",
                f"anullsrc=r={sample_rate}:cl=mono,atrim=duration={gap_seconds[i]}",
            ]
            filter_parts.append(f"[{stream_idx}:a]")
            stream_idx += 1

    n = len(filter_parts)
    concat_filter = "".join(filter_parts) + f"concat=n={n}:v=0:a=1[out]"
    cmd += [
        "-filter_complex", concat_filter,
        "-map", "[out]",
        "-ar", str(sample_rate), "-ac", "1",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=120, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"오디오 연결 실패 (exit={result.returncode}): "
            f"{result.stderr.decode('utf-8', 'replace')[-400:]}"
        )


class TTSEngine(ABC):
    """TTS 엔진 베이스. 각 백엔드(piper/melo/edge)는 본 인터페이스를 구현."""

    name: str           # 'piper' | 'melo' | 'edge'

    @abstractmethod
    def synthesize(
        self,
        *,
        text: str,
        out_path: Path,
        speaker_id: str | None = None,
    ) -> SynthResult:
        """텍스트 → 오디오 파일. out_path 디렉토리는 호출자가 보장."""

    @abstractmethod
    def list_speakers(self) -> list[str]:
        """등록된 화자 ID 목록."""

    def is_available(self) -> bool:
        return True

    def synthesize_segmented(
        self,
        *,
        segments: list[tuple[str, str]],
        out_path: Path,
        speaker_id: str | None = None,
        gaps: tuple[float, ...] = (0.35, 0.50),
    ) -> SynthResult:
        """세그먼트별 개별 합성 후 묵음 갭 삽입 연결 (WAV 출력 엔진 기본 구현).

        segments: [("hook", text), ("body", text), ("twist", text)]
        gaps: 세그먼트 사이 묵음 길이(초) — 순서대로 적용
        metadata["segment_times"]에 정확한 구간 타임라인 반환.
        """
        temp_files: list[Path] = []
        durations: list[float] = []
        gaps_list = list(gaps)

        for i, (name, text) in enumerate(segments):
            tmp = out_path.with_stem(f"_seg{i}_{out_path.stem}")
            result = self.synthesize(text=text, out_path=tmp, speaker_id=speaker_id)
            temp_files.append(result.audio_path)
            durations.append(result.duration_seconds)

        # 정확한 세그먼트 타임라인 계산
        t = 0.0
        segment_times: dict[str, dict[str, float]] = {}
        for i, (name, _) in enumerate(segments):
            segment_times[name] = {"start": round(t, 3), "end": round(t + durations[i], 3)}
            t += durations[i]
            if i < len(segments) - 1 and i < len(gaps_list):
                t += gaps_list[i]

        _concat_audio_with_gaps(temp_files, gaps_list[: len(segments) - 1], out_path, sample_rate=24000)

        for f in temp_files:
            try:
                f.unlink()
            except OSError:
                pass

        total_dur = round(sum(durations) + sum(gaps_list[: len(segments) - 1]), 3)
        return SynthResult(
            audio_path=out_path,
            duration_seconds=total_dur,
            sample_rate=24000,
            speaker_id=speaker_id or "",
            engine=self.name,
            metadata={"segment_times": segment_times},
        )
