"""카드 콘텐츠용 LLM 호출 (Groq → Gemini 폴백, JSON 반환).

분리 원칙:
  - 쇼츠 src/rewriter/ (RewriterChain/RewriteResult) 를 import 하지 않는다.
  - RewriteResult 는 단일 대본(hook/body/twist) 전용이라 카드의 다중 항목 구조에 부적합 (F-02).
  - SDK(groq, google.genai) 를 직접 호출하고 임의 JSON dict 를 반환한다.
  - API 키는 CardSecrets 에서 읽는다 (쇼츠와 동일 .env, 읽기 전용 공유).
"""

from __future__ import annotations

import json
import logging
import re

from cards.config import get_card_secrets

log = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.3-70b-versatile"   # Groq 무료, 카드 카피에 충분한 품질
GEMINI_MODEL = "gemini-2.0-flash"


def _extract_json(raw: str) -> dict:
    if not raw:
        raise ValueError("LLM 빈 응답")
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        raise ValueError(f"JSON 미발견: {raw[:200]}")
    return json.loads(m.group(0))


def _try_groq(prompt: str, *, temperature: float, max_tokens: int) -> dict:
    secrets = get_card_secrets()
    if not secrets.groq_api_key:
        raise RuntimeError("groq_api_key 없음")
    from groq import Groq

    client = Groq(api_key=secrets.groq_api_key, timeout=60.0)
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    return _extract_json(completion.choices[0].message.content or "")


def _try_gemini(prompt: str, *, temperature: float, max_tokens: int) -> dict:
    secrets = get_card_secrets()
    if not secrets.gemini_api_key:
        raise RuntimeError("gemini_api_key 없음")
    import os
    import google.genai as genai
    from google.genai import types as genai_types

    # 쇼츠 gemini_client 와 동일한 SSL 환경 우회 (edge-tts certifi 충돌 방지)
    _ssl = os.environ.pop("SSL_CERT_FILE", None)
    _ca = os.environ.pop("REQUESTS_CA_BUNDLE", None)
    try:
        client = genai.Client(api_key=secrets.gemini_api_key,
                              http_options={"timeout": 120_000})
    finally:
        if _ssl is not None:
            os.environ["SSL_CERT_FILE"] = _ssl
        if _ca is not None:
            os.environ["REQUESTS_CA_BUNDLE"] = _ca

    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
        ),
    )
    return _extract_json(resp.text or "")


def generate_json(prompt: str, *, temperature: float = 0.9, max_tokens: int = 2048) -> dict:
    """프롬프트 → JSON dict. Groq 우선, 실패 시 Gemini 폴백. 모두 실패 시 예외."""
    last: Exception | None = None
    for name, fn in (("groq", _try_groq), ("gemini", _try_gemini)):
        try:
            return fn(prompt, temperature=temperature, max_tokens=max_tokens)
        except Exception as e:
            log.warning("card_llm_failed", extra={"backend": name, "error": repr(e)[:200]})
            last = e
    raise RuntimeError(f"모든 LLM 백엔드 실패: {last!r}")
