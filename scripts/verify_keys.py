"""API 키 라이브 검증 스크립트.

각 API에 가벼운 테스트 호출을 보내 실제로 인증 가능한지 확인한다.
실패 항목은 표시하되 다른 항목 검증은 계속 진행한다.

사용:
    python -m scripts.verify_keys
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings  # noqa: E402


def _ok(name: str, msg: str = "") -> None:
    suffix = f"  ({msg})" if msg else ""
    print(f"  [OK]   {name}{suffix}")


def _skip(name: str, msg: str) -> None:
    print(f"  [SKIP] {name}  ({msg})")


def _fail(name: str, err: str) -> None:
    print(f"  [FAIL] {name}  -> {err}")


# ---------- Gemini ----------
def check_gemini(api_key: str) -> bool:
    if not api_key:
        _skip("Gemini", "GEMINI_API_KEY 미설정")
        return True
    try:
        import google.genai as genai
        from google.genai import types as genai_types

        client = genai.Client(api_key=api_key)
        r = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Reply with the single word: ok",
            config=genai_types.GenerateContentConfig(max_output_tokens=256, temperature=0.1),
        )
        text = (r.text or "").strip()[:60]
        _ok("Gemini", f"response='{text}'" if text else "인증 OK (응답 본문 없음)")
        return True
    except Exception as e:
        _fail("Gemini", repr(e)[:200])
        return False


# ---------- Groq ----------
def check_groq(api_key: str) -> bool:
    if not api_key:
        _skip("Groq", "GROQ_API_KEY 미설정")
        return True
    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "Reply with one word: ok"}],
            max_tokens=10,
            temperature=0.1,
        )
        text = (completion.choices[0].message.content or "").strip()[:30]
        _ok("Groq", f"response='{text}'")
        return True
    except Exception as e:
        _fail("Groq", repr(e)[:200])
        return False


# ---------- Pexels ----------
def check_pexels(api_key: str) -> bool:
    if not api_key:
        _skip("Pexels", "PEXELS_API_KEY 미설정")
        return True
    try:
        import httpx

        r = httpx.get(
            "https://api.pexels.com/videos/search",
            params={"query": "city", "per_page": 1},
            headers={"Authorization": api_key},
            timeout=15.0,
        )
        r.raise_for_status()
        data = r.json()
        total = data.get("total_results", 0)
        _ok("Pexels", f"total_results={total}")
        return True
    except Exception as e:
        _fail("Pexels", repr(e)[:200])
        return False


# ---------- Pixabay ----------
def check_pixabay(api_key: str) -> bool:
    if not api_key:
        _skip("Pixabay", "PIXABAY_API_KEY 미설정")
        return True
    try:
        import httpx

        # Pixabay 공식 API는 Images / Videos만 지원 (Music은 공식 엔드포인트 없음)
        # 키 유효성은 Images API로 확인
        r = httpx.get(
            "https://pixabay.com/api/",
            params={"key": api_key, "q": "test", "per_page": 3},
            timeout=15.0,
        )
        r.raise_for_status()
        data = r.json()
        total = data.get("totalHits", 0)
        _ok("Pixabay", f"totalHits={total} (Images API로 키 유효성 확인. Music API는 공식 미지원)")
        return True
    except Exception as e:
        _fail("Pixabay", repr(e)[:200])
        return False


# ---------- Discord ----------
def check_discord(webhook_url: str) -> bool:
    if not webhook_url:
        _skip("Discord", "DISCORD_WEBHOOK_URL 미설정")
        return True
    try:
        from src.notify.discord_webhook import DiscordNotifier

        notifier = DiscordNotifier(webhook_url=webhook_url)
        ok = notifier.send(
            content="API 키 검증 테스트 메시지입니다.",
            title="[INFO] verify_keys",
            level="INFO",
            extra={"test": "ok", "stage": "verification"},
        )
        if ok:
            _ok("Discord Webhook", "메시지 전송됨")
            return True
        _fail("Discord Webhook", "send returned False")
        return False
    except Exception as e:
        _fail("Discord Webhook", repr(e)[:200])
        return False


# ---------- YouTube OAuth (파일 존재만 검증) ----------
def check_youtube_oauth(secrets) -> bool:
    p = PROJECT_ROOT / secrets.youtube_client_secret_path
    if not p.exists():
        _skip("YouTube OAuth", f"{p.name} 미존재 (구현 단계 후속)")
        return True
    _ok("YouTube OAuth", f"client_secret 발견: {p.name}")
    return True


def main() -> int:
    settings = get_settings()
    s = settings.secrets

    print("=" * 60)
    print(" API 키 라이브 검증 (실제 호출 1회씩)")
    print("=" * 60)

    results = []
    results.append(check_gemini(s.gemini_api_key))
    results.append(check_groq(s.groq_api_key))
    results.append(check_pexels(s.pexels_api_key))
    results.append(check_pixabay(s.pixabay_api_key))
    results.append(check_discord(s.discord_webhook_url))
    results.append(check_youtube_oauth(s))

    print("=" * 60)
    failed = sum(1 for r in results if r is False)
    if failed == 0:
        print(" 모든 검증 통과 (또는 미설정 항목은 skip)")
        return 0
    print(f" 실패: {failed}건")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
