"""크롤 단계 (FR-1).

미사용 소재가 있으면 그것을 사용하고, 없으면 LLMCreatorCrawler로 신규 생성한다.
원문 폐기는 본 단계 시작 시 부수적으로 실행 (FR-1.6).
"""

from __future__ import annotations

from ..crawler.llm_creator import LLMCreatorCrawler
from ..rewriter.chain import RewriterChain
from ..rewriter.gemini_client import GeminiRewriter
from ..rewriter.groq_client import GroqRewriter
from ..rewriter.ollama_client import OllamaRewriter
from ..utils.similarity import is_duplicate, text_sha256
from .context import PipelineContext, StageError, StageSkipped, stage_timer


def run(ctx: PipelineContext) -> int:
    """크롤 단계. 미사용 소재의 ID를 반환."""
    with stage_timer(ctx, "crawl"):
        crawler_cfg = ctx.section("crawler")

        # 1. 24h 경과 원문 폐기 (FR-1.6)
        purged = ctx.repos.sources.purge_raw_text_older_than(
            hours=int(crawler_cfg.get("raw_text_retention_hours", 24))
        )
        if purged:
            ctx.log.info("raw_text_purged", count=purged)

        # 2. 미사용 소재 우선
        existing = ctx.repos.sources.pick_unused(limit=1)
        if existing:
            return int(existing[0]["id"])

        # 3. 신규 수집 (LLM 창작 1순위)
        sources_cfg = crawler_cfg.get("sources", [])
        llm_source_cfg = next(
            (s for s in sources_cfg if s.get("kind") == "llm_creator" and s.get("enabled", True)),
            None,
        )
        if not llm_source_cfg:
            raise StageSkipped("crawler.sources에 활성 llm_creator 항목이 없습니다.")

        themes = list(llm_source_cfg.get("themes", []))
        if not themes:
            raise StageSkipped("llm_creator themes가 비어 있습니다.")

        # LLM 호출은 RewriterChain의 단일 호출 형태로 우회 (creator는 동일 LLM 인프라 사용)
        rewriter_cfg = ctx.section("rewriter")
        chain = _build_rewriter_chain(ctx, rewriter_cfg)

        def llm_call(prompt: str) -> str:
            for backend in chain.backends:
                if not backend.is_available():
                    continue
                try:
                    # LLMCreator는 직접 호출 — RewriterChain.generate는 대본 형식이라 사용 불가
                    # 각 backend의 내부 client에 직접 prompt 전송
                    return _raw_llm_call(backend, prompt)
                except Exception as e:
                    ctx.log.warning("llm_creator_backend_fail", backend=backend.name, error=repr(e))
                    continue
            raise StageError("모든 LLM 백엔드가 사용 불가하거나 실패했습니다.")

        exam_cfg = ctx.section("exam_season")
        crawler = LLMCreatorCrawler(
            themes=themes,
            llm_call=llm_call,
            lucky_charm_themes=list(exam_cfg.get("lucky_charm_themes", [])),
            exam_periods=list(exam_cfg.get("periods", [])),
            lucky_charm_lead_days=int(exam_cfg.get("lucky_charm_lead_days", 7)),
            lucky_charm_ratio=float(exam_cfg.get("lucky_charm_ratio", 0.30)),
        )
        if not crawler.is_available():
            raise StageSkipped("LLMCreatorCrawler가 사용 가능하지 않습니다.")

        existing_motifs = [r["motif"] for r in ctx.repos.sources.pick_unused(limit=200)]
        # 기존 motif 200개 외에 모든 sources 비교 — 너무 무거우면 임베딩 캐시 후속
        threshold = float(crawler_cfg.get("duplicate_threshold_cosine", 0.85))

        new_id: int | None = None
        for result in crawler.fetch(limit=3):
            text_hash = text_sha256(result.motif)
            # 정확 일치 차단
            if ctx.repos.sources.find_by_hash(text_hash):
                ctx.log.info("crawl_duplicate_hash", hash=text_hash[:16])
                continue
            # 임베딩 유사도 차단
            try:
                dup, sim = is_duplicate(result.motif, existing_motifs, threshold=threshold)
            except Exception as e:
                ctx.log.warning("similarity_check_fail_skip", error=repr(e))
                dup, sim = False, 0.0
            if dup:
                ctx.log.info("crawl_duplicate_embedding", similarity=sim)
                continue
            new_id = ctx.repos.sources.insert(
                source_kind=result.source_kind,
                raw_text_hash=text_hash,
                motif=result.motif,
                raw_text=result.raw_text,
                source_site=result.source_site,
                url=result.url,
                title=result.title,
            )
            ctx.log.info("crawl_inserted", source_id=new_id, kind=result.source_kind)
            break

        if new_id is None:
            raise StageError("신규 모티프를 1건도 수집하지 못했습니다.")
        return new_id


def _build_rewriter_chain(ctx: PipelineContext, rewriter_cfg: dict) -> RewriterChain:
    """설정에서 fallback_chain 순서대로 백엔드 인스턴스 생성."""
    backends = []
    chain_order = rewriter_cfg.get("fallback_chain", ["gemini", "groq", "ollama"])
    secrets = ctx.settings.secrets

    for name in chain_order:
        if name == "gemini" and secrets.gemini_api_key:
            cfg = rewriter_cfg.get("gemini", {})
            backends.append(GeminiRewriter(
                api_key=secrets.gemini_api_key,
                model=cfg.get("model", "gemini-2.5-flash"),
                temperature=float(cfg.get("temperature", 0.85)),
                max_output_tokens=int(cfg.get("max_output_tokens", 1024)),
            ))
        elif name == "groq" and secrets.groq_api_key:
            cfg = rewriter_cfg.get("groq", {})
            backends.append(GroqRewriter(
                api_key=secrets.groq_api_key,
                model=cfg.get("model", "llama-3.1-8b-instant"),
                temperature=float(cfg.get("temperature", 0.85)),
                max_tokens=int(cfg.get("max_tokens", 1024)),
            ))
        elif name == "ollama":
            cfg = rewriter_cfg.get("ollama", {})
            backends.append(OllamaRewriter(
                model=cfg.get("model", secrets.ollama_model),
                base_url=cfg.get("base_url", secrets.ollama_base_url),
                temperature=float(cfg.get("temperature", 0.85)),
            ))

    if not backends:
        raise StageSkipped("사용 가능한 LLM 백엔드가 없습니다 (API 키 + Ollama 모두 부재).")
    return RewriterChain(backends)


def _raw_llm_call(backend, prompt: str) -> str:
    """Rewriter 백엔드의 내부 LLM 호출을 우회하여 임의 prompt 전송 (creator용)."""
    backend._ensure_client()  # type: ignore[attr-defined]
    if backend.name == "gemini":
        from google.genai import types as genai_types
        response = backend._client.models.generate_content(  # type: ignore[union-attr]
            model=backend.model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=backend.temperature,
                max_output_tokens=backend.max_output_tokens,
                response_mime_type="application/json",
            ),
        )
        return response.text or ""
    if backend.name == "groq":
        completion = backend._client.chat.completions.create(  # type: ignore[union-attr]
            model=backend.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=backend.temperature,
            max_tokens=backend.max_tokens,
            response_format={"type": "json_object"},
        )
        return completion.choices[0].message.content or ""
    if backend.name == "ollama":
        response = backend._client.generate(  # type: ignore[union-attr]
            model=backend.model,
            prompt=prompt,
            format="json",
            options={"temperature": backend.temperature},
        )
        return response.get("response", "") if isinstance(response, dict) else getattr(response, "response", "")
    raise StageError(f"알 수 없는 backend: {backend.name}")
