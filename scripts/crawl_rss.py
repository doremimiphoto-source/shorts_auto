"""RSS 피드에서 교육 소재를 수집하고 sources DB에 저장한다.

config.yaml의 crawler.sources 중 kind=rss 항목의 feeds를 순회하며:
  1. RSS 파싱 → 제목+요약 키워드 필터
  2. LLM으로 motif 추출 (관련 없으면 skip)
  3. 중복 검사(hash/embedding) 후 DB 저장

실행:
    python -m scripts.crawl_rss [--limit N] [--dry-run]

--limit N   : 피드당 최대 처리 기사 수 (기본 10)
--dry-run   : DB 저장 없이 수집 결과만 출력
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

if sys.stdout is None:
    sys.stdout = open("nul", "w", encoding="utf-8")
else:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

_NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
}

_MOTIF_PROMPT = """너는 YouTube Shorts '중학생 공부법' 채널의 콘텐츠 기획자다.
아래 교육 뉴스 기사를 읽고 중학생에게 유용한 공부 팁 소재가 있는지 판단하라.

[기사 제목]
{title}

[기사 요약]
{description}

[규칙]
- 중학생 공부법과 직접 관련 없으면 반드시 relevant=false 반환.
- relevant=true이면 80~150자 한국어 motif_summary 생성.
  motif_summary는 구체적인 방법·수치·기대효과를 포함한다.
- 욕설·혐오·정치·종교·의료·법률·금융 자문 금지.
- 출력은 JSON만.

[출력 형식]
{{
  "relevant": true | false,
  "motif_summary": "...(relevant=true일 때만)"
}}
"""


def _fetch_rss(url: str, timeout: int = 15) -> list[dict]:
    """RSS URL을 파싱해 [{title, description, link}] 반환."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "ShortsAutoBot/1.0 (educational content aggregator)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except Exception as e:
        print(f"[rss] 피드 요청 실패 ({url}): {e}")
        return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        print(f"[rss] XML 파싱 실패 ({url}): {e}")
        return []

    items: list[dict] = []
    # RSS 2.0
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        desc = (item.findtext("description") or "").strip()
        link = (item.findtext("link") or "").strip()
        if title:
            items.append({"title": title, "description": desc, "link": link})
    # Atom
    if not items:
        ns = _NAMESPACES["atom"]
        for entry in root.iter(f"{{{ns}}}entry"):
            title = (entry.findtext(f"{{{ns}}}title") or "").strip()
            desc = (entry.findtext(f"{{{ns}}}summary") or "").strip()
            link_el = entry.find(f"{{{ns}}}link")
            link = (link_el.get("href", "") if link_el is not None else "").strip()
            if title:
                items.append({"title": title, "description": desc, "link": link})
    return items


def _keyword_match(title: str, desc: str, keywords: list[str], min_hits: int) -> bool:
    text = (title + " " + desc).lower()
    hits = sum(1 for kw in keywords if kw in text)
    return hits >= min_hits


_NON_KO_RE = __import__("re").compile(
    r"[一-鿿"       # CJK 한자
    r"぀-ゟ"        # 히라가나
    r"゠-ヿ"        # 가타카나
    r"㐀-䶿"        # 한자 확장A
    r"＀-￯"        # 전각문자
    r"A-Za-z]",             # 영문자
)


def _is_clean_korean(text: str) -> bool:
    """한글·숫자·공백·기본 구두점만 포함하는지 확인."""
    return not _NON_KO_RE.search(text)


def _llm_extract_motif(title: str, description: str, llm_call) -> str | None:
    """LLM으로 기사에서 motif 추출. 관련 없으면 None 반환."""
    import json, re

    desc_preview = description[:300] if description else "(요약 없음)"
    prompt = _MOTIF_PROMPT.format(title=title, description=desc_preview)
    try:
        response = llm_call(prompt)
    except Exception as e:
        print(f"[rss] LLM 호출 실패: {e}")
        return None

    match = re.search(r"\{[\s\S]*\}", response)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

    if not data.get("relevant"):
        return None
    motif = data.get("motif_summary", "")
    if not isinstance(motif, str):
        return None
    motif = motif.strip()
    if not (50 <= len(motif) <= 400):
        return None
    if not _is_clean_korean(motif):
        return None
    return motif


def main() -> None:
    parser = argparse.ArgumentParser(description="RSS 피드에서 교육 소재 수집")
    parser.add_argument("--limit", type=int, default=10, help="피드당 최대 기사 수 (기본 10)")
    parser.add_argument("--dry-run", action="store_true", help="DB 저장 없이 결과만 출력")
    args = parser.parse_args()

    from src.config import get_settings
    from src.db import open_database
    from src.pipeline.crawl_stage import _build_rewriter_chain, _raw_llm_call
    from src.repository import Repositories
    from src.utils.similarity import is_duplicate, text_sha256

    settings = get_settings()
    crawler_cfg = settings.section("crawler")
    sources_cfg = crawler_cfg.get("sources", [])
    rss_cfg = next((s for s in sources_cfg if s.get("kind") == "rss" and s.get("enabled", True)), None)
    if not rss_cfg:
        print("[rss] config.yaml에 활성 rss 소스가 없습니다.")
        return

    feeds: list[dict] = rss_cfg.get("feeds", [])
    keywords: list[str] = rss_cfg.get("keyword_filter", [])
    min_hits: int = int(rss_cfg.get("min_keyword_hits", 1))
    threshold = float(crawler_cfg.get("duplicate_threshold_cosine", 0.78))

    rewriter_cfg = settings.section("rewriter")

    class _FakePipelineContext:
        """LLM 체인 빌드에 필요한 최소 컨텍스트."""
        def section(self, name):
            return settings.section(name)
        settings_ = settings
        log = type("L", (), {"warning": lambda s, *a, **k: None})()

    ctx = _FakePipelineContext()
    ctx.settings = settings
    chain = _build_rewriter_chain(ctx, rewriter_cfg)  # type: ignore[arg-type]

    def llm_call(prompt: str) -> str:
        for backend in chain.backends:
            if not backend.is_available():
                continue
            try:
                return _raw_llm_call(backend, prompt)
            except Exception as e:
                print(f"[rss] LLM 백엔드 {backend.name} 실패: {e}")
        raise RuntimeError("모든 LLM 백엔드 실패")

    db = open_database(settings.project_path(settings.section("database").get("path", "data/shorts.db")))
    repos = Repositories(db)

    existing_motifs = repos.sources.list_recent_motifs(limit=200)
    total_saved = 0

    for feed in feeds:
        feed_url = feed.get("url", "")
        site_name = feed.get("site", feed_url)
        if not feed_url:
            continue

        print(f"\n[rss] 피드 수집: {site_name} ({feed_url})")
        items = _fetch_rss(feed_url)
        if not items:
            print(f"  → 기사 없음")
            continue

        processed = 0
        for item in items[:args.limit]:
            title = item["title"]
            desc = item["description"]
            link = item["link"]

            if not _keyword_match(title, desc, keywords, min_hits):
                continue

            motif = _llm_extract_motif(title, desc, llm_call)
            if motif is None:
                print(f"  skip (비관련): {title[:40]}")
                continue

            text_hash = text_sha256(motif)
            if repos.sources.find_by_hash(text_hash):
                print(f"  skip (hash중복): {title[:40]}")
                continue

            dup, sim = is_duplicate(motif, existing_motifs, threshold=threshold)
            if dup:
                print(f"  skip (유사도{sim:.2f}): {title[:40]}")
                continue

            print(f"  ✓ 저장: {title[:40]} → {motif[:50]}...")
            if not args.dry_run:
                new_id = repos.sources.insert(
                    source_kind="rss",
                    raw_text_hash=text_hash,
                    motif=motif,
                    raw_text=desc[:1000] if desc else None,
                    source_site=site_name,
                    url=link,
                    title=title[:200],
                )
                existing_motifs.append(motif)
                total_saved += 1
                print(f"     source_id={new_id}")
            else:
                print(f"     [dry-run] 저장 생략")
            processed += 1

        print(f"  → {site_name}: {processed}개 처리")

    db.close()
    print(f"\n[rss] 완료: 총 {total_saved}개 소재 저장")


if __name__ == "__main__":
    main()
