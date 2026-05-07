"""src.utils.similarity 테스트 (해시·코사인 부분만 — 실제 임베딩 호출은 통합 테스트로 분리)."""

from __future__ import annotations

import numpy as np
import pytest

from src.utils.similarity import cosine, cosine_max, cosine_mean, deserialize, serialize, text_sha256


def test_text_sha256_deterministic() -> None:
    a = text_sha256("Hello   world")
    b = text_sha256("Hello world")
    # 공백 정규화로 동일 해시
    assert a == b
    assert len(a) == 64


def test_text_sha256_different() -> None:
    assert text_sha256("a") != text_sha256("b")


def test_cosine_identical_vectors() -> None:
    v = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    assert cosine(v, v) == pytest.approx(1.0, abs=1e-6)


def test_cosine_orthogonal() -> None:
    v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    v2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    assert cosine(v1, v2) == pytest.approx(0.0, abs=1e-6)


def test_cosine_opposite() -> None:
    v1 = np.array([1.0, 0.0], dtype=np.float32)
    v2 = np.array([-1.0, 0.0], dtype=np.float32)
    assert cosine(v1, v2) == pytest.approx(-1.0, abs=1e-6)


def test_cosine_max_corpus() -> None:
    query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    corpus = np.array([
        [0.0, 1.0, 0.0],
        [0.9, 0.1, 0.0],     # 가장 유사
        [-1.0, 0.0, 0.0],
    ], dtype=np.float32)
    # corpus는 정규화된 가정 — 임베딩 함수가 normalize=True 사용
    corpus_norm = corpus / np.linalg.norm(corpus, axis=1, keepdims=True)
    max_sim = cosine_max(query, corpus_norm)
    assert max_sim > 0.9


def test_cosine_mean_corpus() -> None:
    query = np.array([1.0, 0.0], dtype=np.float32)
    corpus = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    mean_sim = cosine_mean(query, corpus)
    # (1 + 1 + 0) / 3
    assert mean_sim == pytest.approx(2.0 / 3.0, abs=1e-6)


def test_serialize_roundtrip() -> None:
    v = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
    blob = serialize(v)
    back = deserialize(blob, dim=4)
    np.testing.assert_array_almost_equal(back, v)
