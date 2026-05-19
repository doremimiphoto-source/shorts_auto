"""채널 분석 결과 디스코드 알림 발송."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from src.config import get_settings
from src.notify.discord_webhook import DiscordNotifier

settings = get_settings()
notifier = DiscordNotifier(webhook_url=settings.secrets.discord_webhook_url)

ok1 = notifier.send(
    title="📊 도도레미 채널 분석 완료",
    level="INFO",
    content=(
        "**채널:** 도도레미(친)텐션  |  구독자: 1명  |  총 조회: 1,593회  |  영상: 12개\n\n"
        "**🏆 조회수 TOP 5**\n"
        "1위 플래너 vs 앱 비교 → **1,415조회** ★ 압도적 1위\n"
        "2위 포모도로 25+5 루틴 → **770조회**\n"
        "3위 중학생 하루 공부 루틴 → **582조회**\n"
        "4위 광물 보고서 만점 꿀팁 → **537조회**\n"
        "5위 중국어 수행평가 발화 → **449조회**\n\n"
        "**❌ 실패 콘텐츠**\n"
        "행운 부적 27조회 / 기출 반복 19조회 / 망각 곡선 8조회\n\n"
        "**💡 핵심 인사이트**\n"
        "A vs B 비교형이 2위(770)보다 2배 높은 압도적 1위\n"
        "루틴·기법 소개 콘텐츠가 꾸준히 상위권\n"
        "lucky_charm(행운 부적)은 완전 실패 → 비활성화"
    ),
    extra={
        "채널 총 조회": "1,593회",
        "구독자": "1명 (초기)",
        "최고 영상": "플래너vs앱 1,415조회",
        "분석 영상 수": "12개",
    }
)

ok2 = notifier.send(
    title="⚙️ 콘텐츠 전략 업데이트 완료",
    level="SUCCESS",
    content=(
        "채널 데이터 기반 config 전면 재편 완료\n\n"
        "**추가된 TIER 1 비교형 테마 (10개)**\n"
        "공부 앱 vs 종이 플래너\n"
        "혼자 공부 vs 스터디카페\n"
        "음악 들으며 공부 vs 조용히 공부\n"
        "교재 정독 vs 기출 반복\n"
        "밤 공부 vs 아침 공부 외 5개\n\n"
        "**hook_pattern 변경**\n"
        "comparison 신규 추가 → 1순위 배치\n"
        "lucky_charm 완전 제거 (조회수 27 실패)\n\n"
        "**테마 총 40개로 확장** (TIER 1~4 구조화)\n"
        "TIER 1 비교형 10개 / TIER 2 루틴형 8개\n"
        "TIER 3 수행평가 10개 / TIER 4 공부법 8개\n\n"
        "lucky_charm_ratio: 0.15 → 0.0 (완전 비활성)"
    ),
    extra={
        "비교형 신규 테마": "10개",
        "hook_pattern": "comparison 추가",
        "lucky_charm": "완전 비활성화",
        "총 테마 수": "40개",
    }
)

ok3 = notifier.send(
    title="🚀 구독자·조회수 증가 추천 콘텐츠",
    level="INFO",
    content=(
        "채널 성장을 위한 추가 추천 콘텐츠 전략\n\n"
        "**즉시 제작 추천 (조회수 극대화)**\n"
        "시리즈화: A vs B 비교 시리즈 (채널 정체성 확립)\n"
        "기말고사 D-14/D-7/D-1 카운트다운 루틴 시리즈\n"
        "초초단편: 3초 공부 꿀팁 포맷 실험\n\n"
        "**구독자 증가 전략**\n"
        "시리즈 연속성: 혼자공부 vs 카페 → 아침 vs 밤 → 교재 vs 기출\n"
        "댓글 참여 유도: 너는 어떤 편? 양자택일 질문으로 마무리\n"
        "업로드 일관성: 매일 07:00 / 18:00 / 22:00 고정\n\n"
        "**채널 고정 영상 추천**\n"
        "현재 1위 플래너 vs 앱 영상을 채널 상단 고정 권장\n\n"
        "**신규 생성 완료: video_44.mp4**\n"
        "혼자 공부 vs 스터디카페 — 성적 올리는 진짜 선택법\n"
        "배경: 도서관 실사 영상 | 길이: 25.8초"
    ),
    extra={
        "신규 영상": "video_44.mp4",
        "hook 패턴": "comparison (A vs B)",
        "배경": "library_quiet_reading 실사",
        "업로드 대기": "유튜브 업로드 필요 시 알려주세요",
    }
)

print("Discord 전송:", "모두 성공" if (ok1 and ok2 and ok3) else f"일부 실패: {ok1} {ok2} {ok3}")
