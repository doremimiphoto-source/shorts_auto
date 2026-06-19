"""Groq llama-3.1-8b-instant agentic loop (OpenAI-compatible tool calling).

배치(llama-3.3-70b-versatile)와 모델이 달라 TPM 풀이 완전히 분리됨.
Gemini 일일 쿼터 소진 시에도 독립적으로 동작.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any

from groq import Groq

from . import tools as T

log = logging.getLogger(__name__)

MODEL = "llama-3.1-8b-instant"   # 봇 전용 — 배치의 70b-versatile과 TPM 풀 분리
MAX_HISTORY = 20                   # system 제외 메시지 수
MAX_ITER = 6

SYSTEM_PROMPT = """\
당신은 "shorts_auto" YouTube Shorts 자동화 파이프라인의 원격 제어 어시스턴트입니다.
사용자(채널 운영자)가 모바일에서 자연어로 파이프라인을 모니터링하고 제어할 수 있도록 돕습니다.

## 프로젝트 정보
- 채널: 도도레미 (중학생 공부 Shorts)
- 파이프라인: crawl → rewrite(LLM) → TTS → subtitle → render → upload(YouTube)

## LLM 구성
- Primary: Gemini 2.0-flash (무료 RPM 15, RPD 1500)
- Fallback: Groq llama-3.3-70b-versatile (무료 TPM 6000/분)

## 배치 스케줄 (KST)
- 06:00 / 14:30 / 17:30 / 21:00 — 중학생 피크 30~60분 전 업로드 목적

## YouTube 쿼터
- 일일 한도: 10,000 units / 업로드당: 1,600 units → 하루 최대 6건 (목표 4건)

## 도구 사용 원칙
1. run_batch 전에 반드시 get_status로 현황 확인할 것
2. killswitch 조작 전 이유 설명할 것
3. 에러 분석 시 원인과 해결 방안을 함께 제시할 것

응답은 한국어로, 간결하게 작성하세요.
"""

# OpenAI-compatible tool schema
TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_status",
            "description": "파이프라인 현황 조회 — 오늘 업로드 수, YouTube 쿼터, 미사용 소재, 최근 에러, 킬스위치 상태",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_logs",
            "description": "오늘 JSON 로그 조회. level(error/warning/info)과 stage(crawl/rewrite/tts/subtitle/render/upload)로 필터 가능",
            "parameters": {
                "type": "object",
                "properties": {
                    "n":     {"type": "integer", "description": "반환할 최대 항목 수 (기본 50)"},
                    "level": {"type": "string",  "description": "로그 레벨 필터"},
                    "stage": {"type": "string",  "description": "파이프라인 단계 필터"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_batch",
            "description": "배치 파이프라인 즉시 실행. count 1~3건. 킬스위치 활성 시 거부. 최대 10분 소요",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "생성할 영상 수 (1~3, 기본 1)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_killswitch",
            "description": "배치 실행 킬스위치. enable=true → 다음 배치부터 중단, enable=false → 재개",
            "parameters": {
                "type": "object",
                "properties": {
                    "enable": {"type": "boolean", "description": "true=중단 / false=재개"},
                },
                "required": ["enable"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "프로젝트 내 허용된 파일 열람. 허용 경로: config.yaml, prompts/, logs/, data/concept_log.jsonl",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "프로젝트 루트 기준 상대 경로 (예: config.yaml)"},
                },
                "required": ["path"],
            },
        },
    },
]


def _execute_tool(name: str, args: dict) -> Any:
    if name == "get_status":     return T.get_status()
    if name == "read_logs":      return T.read_logs(n=int(args.get("n", 50)), level=args.get("level"), stage=args.get("stage"))
    if name == "run_batch":      return T.run_batch(count=int(args.get("count", 1)))
    if name == "set_killswitch": return T.set_killswitch(enable=bool(args["enable"]))
    if name == "read_file":      return T.read_file(path=args["path"])
    return {"error": f"알 수 없는 도구: {name}"}


# user_id → 메시지 히스토리 (system 메시지 제외)
_histories: dict[int, list[dict]] = defaultdict(list)


class Agent:
    def __init__(self, api_key: str) -> None:
        self._client = Groq(api_key=api_key)

    def process(self, user_message: str, user_id: int = 0) -> str:
        """사용자 메시지 처리 → 도구 호출(필요 시) → 최종 응답 반환."""
        history = _histories[user_id]
        history.append({"role": "user", "content": user_message})

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

        for _ in range(MAX_ITER):
            response = self._client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=2048,
            )

            msg = response.choices[0].message
            messages.append(msg)

            # 도구 호출 없음 → 텍스트 응답
            if not msg.tool_calls:
                text = msg.content or "(응답 없음)"
                # history에 assistant 응답 추가
                history.append({"role": "assistant", "content": text})
                _trim_history(history)
                return text

            # 도구 실행
            history.append({"role": "assistant", "content": msg.content, "tool_calls": [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]})

            for tc in msg.tool_calls:
                log.info("tool_call name=%s", tc.function.name)
                try:
                    args = json.loads(tc.function.arguments)
                    result = _execute_tool(tc.function.name, args)
                except Exception as exc:
                    result = {"error": str(exc)}

                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
                messages.append(tool_msg)
                history.append(tool_msg)

        _trim_history(history)
        return "처리 중 예상치 못한 오류가 발생했습니다."

    def clear_history(self, user_id: int) -> None:
        _histories[user_id].clear()


def _trim_history(history: list) -> None:
    while len(history) > MAX_HISTORY:
        history.pop(0)
