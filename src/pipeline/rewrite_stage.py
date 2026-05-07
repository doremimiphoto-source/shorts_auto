"""대본 생성 단계 (FR-2).

- LLM 폴백 체인 호출
- 콘텐츠 필터 (FR-2.5)
- Hook 패턴 순환 (FR-2.7)
- 3중 유사도 검증 (FR-2.6)
"""

from __future__ import annotations

from ..utils.content_filter import ContentFilter
from ..utils.hook_pattern import select_hook_pattern
from ..utils.similarity import cosine_max, cosine_mean, encode, serialize, text_sha256
from .context import PipelineContext, StageError, StageSkipped, stage_timer
from .crawl_stage import _build_rewriter_chain


_DEFAULT_HOOK_POOL = [
    "question", "shock", "number", "dialogue",
    "confession", "twist_preview", "timeline", "second_person",
]


def run(ctx: PipelineContext, *, source_id: int) -> int:
    """대본 생성 단계. script_id 반환."""
    with stage_timer(ctx, "rewrite") as state:
        row = ctx.repos.db.fetchone("SELECT * FROM sources WHERE id = ?", (source_id,))
        if row is None:
            raise StageError(f"source_id={source_id} 미존재")

        rewriter_cfg = ctx.section("rewriter")
        chain = _build_rewriter_chain(ctx, rewriter_cfg)

        # 1. Hook 패턴 선택 (FR-2.7)
        hook_cfg = rewriter_cfg.get("hook_patterns", {})
        pool = list(hook_cfg.get("pool", _DEFAULT_HOOK_POOL))
        recent_hooks = ctx.repos.scripts.list_recent_hook_patterns(
            limit=int(hook_cfg.get("no_repeat_window", 5))
        )
        hook_pattern = select_hook_pattern(
            pool=pool,
            recent_used=recent_hooks,
            no_repeat_window=int(hook_cfg.get("no_repeat_window", 5)),
            seed=row["motif"][:64],
        )
        ctx.log.info("hook_selected", pattern=hook_pattern, recent=recent_hooks)

        # 2. 프롬프트 로드
        prompt_path = ctx.project_root / "prompts" / "story_rewrite.txt"
        if not prompt_path.exists():
            raise StageError(f"프롬프트 파일 미존재: {prompt_path}")
        prompt_template = prompt_path.read_text(encoding="utf-8")

        # 3. LLM 호출 (글자 수 미달 시 최대 2회 재시도)
        theme = row.get("title") or "사연"
        min_chars = int(rewriter_cfg.get("output", {}).get("target_korean_chars", 100)) - 15
        result = None
        for attempt in range(3):
            result = chain.generate(
                theme=theme,
                motif=row["motif"],
                hook_pattern=hook_pattern,
                prompt_template=prompt_template,
            )
            char_len = len(result.full_text)
            if char_len >= min_chars:
                break
            ctx.log.warning("rewrite_too_short", attempt=attempt + 1, chars=char_len, min=min_chars)
        assert result is not None

        # 4. 콘텐츠 필터 (FR-2.5)
        filter_cfg = rewriter_cfg.get("content_filter", {})
        block_path = filter_cfg.get("block_keywords_path", "prompts/block_keywords.txt")
        cf = ContentFilter.from_file(ctx.project_root / block_path, mode="drop")
        check = cf.check(result.full_text)
        if not check.allowed:
            ctx.log.warning("content_filter_blocked", keywords=check.matched_keywords)
            raise StageError(f"콘텐츠 필터 위반: {check.matched_keywords}")

        # 5. 유사도 3중 검증 (FR-2.6)
        sim_cfg = rewriter_cfg.get("similarity", {})
        embedding_model = sim_cfg.get("embedding_model", "jhgan/ko-sroberta-multitask")
        cand_vec = encode(result.full_text, model_name=embedding_model)

        # ① motif 대비
        motif_vec = encode(row["motif"], model_name=embedding_model)
        sim_motif = float(cosine_max(cand_vec, motif_vec.reshape(1, -1)))
        # ② 30일 대비
        recent_30d = ctx.repos.scripts.list_recent(days=30, limit=200)
        sim_30d = _max_similarity(cand_vec, [s["full_text"] for s in recent_30d if s.get("full_text")], embedding_model) if recent_30d else 0.0
        # ③ 누적 평균
        cum_sample = ctx.repos.scripts.sample_cumulative(limit=100)
        sim_cum = _mean_similarity(cand_vec, [s["full_text"] for s in cum_sample if s.get("full_text")], embedding_model) if cum_sample else 0.0

        ctx.log.info("similarity_checks",
                     sim_motif=round(sim_motif, 4),
                     sim_30d=round(sim_30d, 4),
                     sim_cum=round(sim_cum, 4))

        # lucky_charm은 구조적으로 같은 전설을 반복하므로 30일 임계값 완화
        hook_used = result.hook_pattern_used or hook_pattern
        if hook_used == "lucky_charm":
            thresh_30d = float(sim_cfg.get("lucky_charm_30d_max", 0.88))
        else:
            thresh_30d = float(sim_cfg.get("recent_30d_max", 0.72))

        def _block_source(reason: str) -> None:
            ctx.repos.sources.mark_status(source_id, "similarity_blocked")
            ctx.log.warning("source_blocked", source_id=source_id, reason=reason)

        if sim_motif >= float(sim_cfg.get("motif_max", 0.97)):
            _block_source(f"motif 유사도 초과: {sim_motif:.3f}")
            raise StageSkipped(f"motif 유사도 초과: {sim_motif:.3f}")
        if sim_30d >= thresh_30d:
            _block_source(f"30일 유사도 초과: {sim_30d:.3f}")
            raise StageSkipped(f"30일 유사도 초과: {sim_30d:.3f}")
        if sim_cum >= float(sim_cfg.get("cumulative_sample_max", 0.55)):
            _block_source(f"누적 평균 유사도 초과: {sim_cum:.3f}")
            raise StageSkipped(f"누적 평균 유사도 초과: {sim_cum:.3f}")

        # 6. DB 저장
        script_id = ctx.repos.scripts.insert(
            source_id=source_id,
            hook=result.hook,
            body=result.body,
            twist=result.twist,
            full_text=result.full_text,
            title=result.title,
            hashtags=result.hashtags,
            hook_pattern=result.hook_pattern_used or hook_pattern,
            similarity_motif=sim_motif,
            similarity_30d=sim_30d,
            similarity_cum=sim_cum,
            model_used=result.model_used,
            model_version=result.model_version,
            embedding=serialize(cand_vec),
        )
        ctx.repos.sources.mark_status(source_id, "used")
        state["message"] = f"script_id={script_id}, model={result.model_used}"
        return script_id


def _max_similarity(query_vec, texts: list[str], model_name: str) -> float:
    if not texts:
        return 0.0
    corpus = encode(texts, model_name=model_name)
    return float(cosine_max(query_vec, corpus))


def _mean_similarity(query_vec, texts: list[str], model_name: str) -> float:
    if not texts:
        return 0.0
    corpus = encode(texts, model_name=model_name)
    return float(cosine_mean(query_vec, corpus))
