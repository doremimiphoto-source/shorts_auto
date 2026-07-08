"""카드 콘텐츠 파이프라인 오케스트레이터 — @HiddenFindsDaily.

  python -m cards.main --vertical v2 --platform pinterest --dry-run   # 여행
  python -m cards.main --vertical v3 --platform pinterest --dry-run   # K-뷰티
  python -m cards.main --vertical v2 --platform pinterest             # 실업로드

분리 원칙: src/ 를 import 하지 않는다 (cards/ 자족).
"""

from __future__ import annotations

import argparse
import datetime
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from cards.config import AFFILIATE_DISCLOSURE, HASHTAGS, LINKTREE_URL, VERTICAL_OUTPUT
from cards.db import (open_cards_db, record_upload, save_affiliate_link,
                      save_content, title_exists)
from cards.renderer import CarouselRenderer, Slide

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("cards.main")


def _campaign_id(seq: int = 1) -> str:
    return f"{datetime.datetime.utcnow():%Y%m%d}_{seq:03d}"


def _hashtag_str(vertical: str, n: int = 20) -> str:
    return " ".join(f"#{t}" for t in HASHTAGS.get(vertical, [])[:n])


@dataclass
class PinJob:
    """버티컬별로 채워서 _publish_pinterest 에 넘기는 업로드 작업."""
    vertical: str            # 'v2_travel' | 'v3_kbeauty'
    short_vertical: str      # 'v2' | 'v3'
    title: str
    subtitle: str
    slides: list[Slide]
    slides_json: str
    summary: str             # 핀 설명용 항목 요약
    partner: str             # 어필리에이트 파트너
    partner_base_url: str


def _publish_pinterest(job: PinJob, *, dry_run: bool) -> int:
    from cards.affiliate.links import build_link
    from cards.uploader.pinterest import upload_pin, board_for_vertical, PinterestError

    platform = "pinterest"
    db = open_cards_db()

    if title_exists(db, job.vertical, job.title):
        log.warning("중복 제목 — 재생성 권장: %s", job.title)

    # 렌더 (Pinterest 2:3)
    out_dir = VERTICAL_OUTPUT[job.vertical] / _campaign_id()
    paths = CarouselRenderer().render(job.slides, "pinterest", out_dir)
    log.info("rendered %d slides → %s", len(paths), out_dir)

    # 어필리에이트 링크 + UTM
    campaign = _campaign_id()
    affiliate_url = build_link(job.partner, platform=platform,
                               vertical=job.short_vertical, campaign=campaign)

    # DB 저장
    content_id = save_content(db, vertical=job.vertical, title=job.title,
                              hook_text=job.title, slides_json=job.slides_json)
    save_affiliate_link(db, vertical=job.short_vertical, product_id=job.vertical,
                        platform=platform, partner=job.partner,
                        original_url=job.partner_base_url,
                        tracking_url=affiliate_url, utm_campaign=campaign)

    # 핀 설명
    description = (
        f"{job.title}\n{job.subtitle}\n\n"
        f"📌 {job.summary}\n\n"
        f"🔗 {LINKTREE_URL}\n\n"
        f"{AFFILIATE_DISCLOSURE}\n\n{_hashtag_str(job.vertical)}"
    )

    pin_image = paths[0]   # HOOK 슬라이드 = 단일 정적 핀
    if dry_run:
        log.info("[DRY-RUN] 업로드 생략:")
        log.info("  image: %s", pin_image)
        log.info("  link : %s", affiliate_url)
        log.info("  desc : %s", description.replace("\n", " | ")[:220])
        record_upload(db, content_id=content_id, platform=platform, post_id=None,
                      image_ratio="2:3", status="dry_run")
        db.close()
        return 0

    from cards import notify
    try:
        pin_id = upload_pin(board_id=board_for_vertical(job.vertical),
                            image_path=pin_image, title=job.title,
                            description=description, link=affiliate_url)
        record_upload(db, content_id=content_id, platform=platform, post_id=pin_id,
                      image_ratio="2:3", status="success")
        log.info("✅ Pinterest 핀 업로드 성공: %s", pin_id)
        notify.notify_success(vertical=job.short_vertical, platform=platform,
                              title=job.title, post_id=pin_id)
        db.close()
        return 0
    except PinterestError as e:
        record_upload(db, content_id=content_id, platform=platform, post_id=None,
                      image_ratio="2:3", status="failed", error_msg=str(e))
        log.error("❌ Pinterest 업로드 실패: %s", e)
        notify.notify_failed(vertical=job.short_vertical, platform=platform, error=str(e))
        db.close()
        return 1


def _build_caption(job: PinJob, affiliate_url: str) -> str:
    """수동 게시용 캡션 (제목·요약·링크트리·어필리에이트 공시·해시태그)."""
    return (
        f"{job.title}\n{job.subtitle}\n\n"
        f"📌 {job.summary}\n\n"
        f"🔗 Links in bio: {LINKTREE_URL}\n\n"
        f"{AFFILIATE_DISCLOSURE}\n\n"
        f"{_hashtag_str(job.vertical)}\n\n"
        f"---\n[게시자 참고 — 캡션엔 넣지 말 것]\n"
        f"어필리에이트 링크: {affiliate_url}"
    )


def run_export(job: PinJob) -> int:
    """수동 게시용 내보내기 — 전체 캐러셀을 3비율로 렌더 + caption.txt. 업로드/API 없음."""
    from cards.affiliate.links import build_link
    campaign = _campaign_id()
    out_dir = VERTICAL_OUTPUT[job.vertical] / f"export_{campaign}"
    renderer = CarouselRenderer()

    counts = {}
    for ratio in ("pinterest", "instagram", "tiktok"):
        paths = renderer.render(job.slides, ratio, out_dir / ratio)
        counts[ratio] = len(paths)

    affiliate_url = build_link(job.partner, platform="manual",
                               vertical=job.short_vertical, campaign=campaign)
    (out_dir / "caption.txt").write_text(_build_caption(job, affiliate_url), encoding="utf-8")

    # DB 기록 (중복 방지용 제목 저장)
    db = open_cards_db()
    save_content(db, vertical=job.vertical, title=job.title,
                 hook_text=job.title, slides_json=job.slides_json)
    db.close()

    log.info("✅ 수동 게시용 내보내기 완료")
    print(f"\n📁 {out_dir}")
    print(f"   ├─ pinterest/  ({counts.get('pinterest',0)}장, 2:3)")
    print(f"   ├─ instagram/  ({counts.get('instagram',0)}장, 4:5)")
    print(f"   ├─ tiktok/     ({counts.get('tiktok',0)}장, 9:16)")
    print(f"   └─ caption.txt (제목·해시태그·공시)")
    print(f"\n→ 각 플랫폼 앱에서 해당 비율 폴더 이미지 + caption 붙여넣기로 수동 게시")
    return 0


def run_v2(*, count: int, region: str, theme: str, dry_run: bool, export: bool) -> int:
    from cards.crawler.travel import generate_travel, to_slides, slides_to_json
    log.info("V2 여행 콘텐츠 생성: %s / %s", region, theme)
    c = generate_travel(region, theme, count=count)
    slides = to_slides(c)
    job = PinJob(
        vertical="v2_travel", short_vertical="v2",
        title=c.title, subtitle=c.subtitle, slides=slides,
        slides_json=slides_to_json(slides),
        summary=" · ".join(p.get("name", "") for p in c.places[:5]),
        partner="booking", partner_base_url="https://www.booking.com",
    )
    return run_export(job) if export else _publish_pinterest(job, dry_run=dry_run)


def run_v1(*, count: int, dry_run: bool, export: bool) -> int:
    from cards.crawler.shopping import generate_shopping, to_slides, slides_to_json
    log.info("V1 쇼핑 비교 콘텐츠 생성 (AliExpress vs Amazon)")
    db_tmp = open_cards_db()
    c = generate_shopping(db_tmp, count=count)
    db_tmp.close()
    slides = to_slides(c)
    job = PinJob(
        vertical="v1_shopping", short_vertical="v1",
        title=c.title, subtitle=c.subtitle, slides=slides,
        slides_json=slides_to_json(slides),
        summary=" · ".join(i.product_name for i in c.items[:5]),
        partner="aliexpress", partner_base_url="https://www.aliexpress.com",
    )
    return run_export(job) if export else _publish_pinterest(job, dry_run=dry_run)


def run_v3(*, count: int, category: str, dry_run: bool, export: bool) -> int:
    from cards.crawler.kbeauty import generate_kbeauty, to_slides, slides_to_json
    log.info("V3 K-뷰티 콘텐츠 생성: %s", category)
    c = generate_kbeauty(category, count=count)
    slides = to_slides(c)
    job = PinJob(
        vertical="v3_kbeauty", short_vertical="v3",
        title=c.title, subtitle=c.subtitle, slides=slides,
        slides_json=slides_to_json(slides),
        summary=" · ".join(p.name_en for p in c.products[:5]),
        partner="yesstyle", partner_base_url="https://www.yesstyle.com",
    )
    return run_export(job) if export else _publish_pinterest(job, dry_run=dry_run)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HiddenFindsDaily 카드 파이프라인")
    ap.add_argument("--vertical", default="v2", choices=["v1", "v2", "v3"])
    ap.add_argument("--platform", default="pinterest", choices=["pinterest", "instagram", "tiktok"])
    ap.add_argument("--count", type=int, default=7)  # 7항목+훅+CTA=9장 (8~10 최적)
    ap.add_argument("--region", default="Southeast Asia")
    ap.add_argument("--theme", default="secret beaches with few tourists")
    ap.add_argument("--category", default="serum", help="V3 K-뷰티 카테고리")
    ap.add_argument("--auto", action="store_true",
                    help="날짜 기반 주제 자동 선택 (launchd 자동화용)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--export", action="store_true",
                    help="수동 게시용 내보내기 (3비율 전체 캐러셀 + caption.txt, 업로드/API 없음)")
    args = ap.parse_args(argv)

    if not args.export and args.platform != "pinterest":
        log.error("아직 미구현 플랫폼: %s (자동 업로드는 pinterest만, 수동은 --export)", args.platform)
        return 2

    try:
        if args.vertical == "v1":
            return run_v1(count=args.count, dry_run=args.dry_run, export=args.export)
        if args.vertical == "v2":
            region, theme = args.region, args.theme
            if args.auto:
                from cards.topics import pick_v2
                region, theme = pick_v2()
                log.info("auto 주제 선택: %s / %s", region, theme)
            return run_v2(count=args.count, region=region, theme=theme,
                          dry_run=args.dry_run, export=args.export)
        if args.vertical == "v3":
            category = args.category
            if args.auto:
                from cards.topics import pick_v3
                category = pick_v3()
                log.info("auto 카테고리 선택: %s", category)
            return run_v3(count=args.count, category=category,
                          dry_run=args.dry_run, export=args.export)
    except Exception as e:
        # 콘텐츠 생성/렌더 단계 예외 → 텔레그램 알림 후 실패 반환
        from cards import notify
        log.exception("파이프라인 오류")
        notify.notify_error(context=f"{args.vertical}/{args.platform}", error=repr(e))
        return 1

    log.error("아직 미구현 버티컬: %s (현재 v2/v3)", args.vertical)
    return 2


if __name__ == "__main__":
    sys.exit(main())
