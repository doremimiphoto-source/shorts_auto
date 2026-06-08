"""유사도 계산 (FR-1.5, FR-2.6).

- SHA-256 정확 일치 검사
- ko-sroberta 임베딩 + 코사인 유사도

`sentence-transformers`는 첫 호출 시 모델을 다운로드하므로 lazy 로딩한다.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


_DEFAULT_MODEL = "jhgan/ko-sroberta-multitask"


def text_sha256(text: str) -> str:
    """원문 SHA-256 해시 (FR-1.5 ①). 공백 정규화 후 해시."""
    normalized = " ".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@lru_cache(maxsize=2)
def _load_model(model_name: str) -> "SentenceTransformer":
    import os
    # 로컬 캐시 강제 사용 — 네트워크 장애 시에도 안정 동작
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def encode(text: str | list[str], model_name: str = _DEFAULT_MODEL) -> np.ndarray:
    """텍스트(들)를 임베딩으로 변환. 단일 문자열은 1D, 리스트는 2D 반환."""
    model = _load_model(model_name)
    arr = model.encode(text, normalize_embeddings=True, convert_to_numpy=True)
    return np.asarray(arr, dtype=np.float32)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """단일 벡터 간 코사인 유사도. `encode()`가 normalize=True를 사용하므로 dot product와 동일."""
    a_n = a / (np.linalg.norm(a) + 1e-12)
    b_n = b / (np.linalg.norm(b) + 1e-12)
    return float(np.dot(a_n, b_n))


def cosine_max(query: np.ndarray, corpus: np.ndarray) -> float:
    """`query` (1D) 와 `corpus` (2D) 의 최대 코사인 유사도."""
    if corpus.ndim == 1:
        return cosine(query, corpus)
    sims = corpus @ (query / (np.linalg.norm(query) + 1e-12))
    return float(np.max(sims))


def cosine_mean(query: np.ndarray, corpus: np.ndarray) -> float:
    """`query` 와 `corpus` 의 평균 코사인 유사도 (FR-2.6 ③ 누적 평균)."""
    if corpus.ndim == 1:
        return cosine(query, corpus)
    sims = corpus @ (query / (np.linalg.norm(query) + 1e-12))
    return float(np.mean(sims))


def is_duplicate(
    candidate_text: str,
    existing_texts: list[str],
    *,
    threshold: float = 0.85,
    model_name: str = _DEFAULT_MODEL,
) -> tuple[bool, float]:
    """후보 텍스트가 기존 텍스트들 중 어느 하나와 임계값 이상 유사한지 검사 (FR-1.5 ②).

    Returns
    -------
    (duplicate, max_similarity)
    """
    if not existing_texts:
        return False, 0.0
    cand_vec = encode(candidate_text, model_name=model_name)
    corpus_vec = encode(existing_texts, model_name=model_name)
    sim = cosine_max(cand_vec, corpus_vec)
    return sim >= threshold, sim


def serialize(vec: np.ndarray) -> bytes:
    """SQLite BLOB 저장용 직렬화."""
    return vec.astype(np.float32).tobytes()


def deserialize(blob: bytes, dim: int = 768) -> np.ndarray:
    """SQLite BLOB → numpy 1D vector. ko-sroberta 기본 차원은 768."""
    arr = np.frombuffer(blob, dtype=np.float32)
    if arr.size % dim == 0:
        return arr.reshape(-1, dim) if arr.size > dim else arr
    return arr
