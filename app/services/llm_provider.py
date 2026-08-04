import json
import re
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from typing import Any, Literal, Protocol

import httpx
from fastapi import HTTPException, status
from openai import APIError, APITimeoutError, AsyncOpenAI
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.interview import InterviewQuestion, InterviewSourceChunk, LiveInterviewTurn


Difficulty = Literal["easy", "medium", "hard"]
ScoreLevel = Literal["weak", "basic", "good", "strong"]


class LLMProvider(Protocol):
    name: str

    async def generate_questions(
        self,
        prompt: str,
        focus: str,
        question_count: int,
        chunks: Sequence[InterviewSourceChunk],
    ) -> list[InterviewQuestion]:
        raise NotImplementedError

    async def score_answer(
        self,
        prompt: str,
        question: str,
        answer: str,
        chunks: Sequence[InterviewSourceChunk],
    ) -> tuple[int, str, list[str], list[str], list[str]]:
        raise NotImplementedError

    async def generate_follow_up(
        self,
        prompt: str,
        question: str,
        answer: str,
        chunks: Sequence[InterviewSourceChunk],
    ) -> tuple[str, str]:
        raise NotImplementedError

    async def generate_live_interview_turn(
        self,
        system_prompt: str,
        turn_prompt: str,
        chunks: Sequence[InterviewSourceChunk],
        *,
        opening: bool,
        ask_next_question: bool,
    ) -> LiveInterviewTurn:
        raise NotImplementedError

    async def stream_live_interview_turn(
        self,
        system_prompt: str,
        turn_prompt: str,
        chunks: Sequence[InterviewSourceChunk],
        *,
        opening: bool,
        ask_next_question: bool,
    ) -> AsyncIterator[str]:
        raise NotImplementedError


class MockLLMProvider:
    name = "mock"

    async def generate_questions(
        self,
        prompt: str,
        focus: str,
        question_count: int,
        chunks: Sequence[InterviewSourceChunk],
    ) -> list[InterviewQuestion]:
        del prompt
        difficulties: list[Difficulty] = ["easy", "medium", "hard"]
        questions: list[InterviewQuestion] = []
        for index in range(question_count):
            chunk = chunks[index % len(chunks)]
            keywords = _keywords_or_defaults(chunk)
            keyword_text = ", ".join(keywords[:3])
            difficulty = difficulties[min(index, len(difficulties) - 1)]
            questions.append(
                InterviewQuestion(
                    question_id=f"mock-q-{index + 1}",
                    difficulty=difficulty,
                    question=(
                        f"结合你简历中关于 {keyword_text} 的经历，说明你在 "
                        f"{focus} 场景下是如何设计、实现并验证效果的？"
                    ),
                    expected_points=[
                        f"能解释 {keywords[0]} 的具体使用场景",
                        "能说明关键技术选择背后的原因",
                        "能讲清楚遇到的问题、排查方法和结果",
                    ],
                    source_chunk_indexes=[chunk.chunk_index],
                )
            )
        return questions

    async def score_answer(
        self,
        prompt: str,
        question: str,
        answer: str,
        chunks: Sequence[InterviewSourceChunk],
    ) -> tuple[int, str, list[str], list[str], list[str]]:
        del prompt
        answer_lower = answer.lower()
        keywords = _unique_keywords(chunks)
        matched_keywords = [keyword for keyword in keywords if keyword in answer_lower]

        score = 45
        score += min(len(answer) // 80, 20)
        score += min(len(matched_keywords) * 6, 30)
        if any(word in answer for word in ["因为", "权衡", "tradeoff", "排查", "验证"]):
            score += 5
        score = max(0, min(score, 100))

        if score >= 85:
            level = "strong"
        elif score >= 70:
            level = "good"
        elif score >= 55:
            level = "basic"
        else:
            level = "weak"

        strengths = [
            "回答覆盖了简历中的关键技术点",
            "回答和问题目标保持相关",
        ]
        if not matched_keywords:
            strengths = ["回答给出了基本方向，但和简历片段的关联还不明显"]

        improvements = []
        if len(answer) < 120:
            improvements.append("补充更具体的实现步骤、异常场景和验证方式")
        missing_keywords = [keyword for keyword in keywords if keyword not in matched_keywords]
        if missing_keywords:
            improvements.append(f"可以主动关联简历中的 {', '.join(missing_keywords[:3])}")
        if not improvements:
            improvements.append("进一步量化结果，例如性能、稳定性或用户影响")

        reference_points = [
            f"问题关注：{question[:80]}",
            *[f"简历关键词：{keyword}" for keyword in matched_keywords[:5]],
        ]
        if len(reference_points) == 1:
            reference_points.append("暂无明显关键词命中，建议回到简历片段补充证据")

        return score, level, strengths, improvements, reference_points

    async def generate_follow_up(
        self,
        prompt: str,
        question: str,
        answer: str,
        chunks: Sequence[InterviewSourceChunk],
    ) -> tuple[str, str]:
        del prompt
        answer_lower = answer.lower()
        missing_keywords = [
            keyword for keyword in _unique_keywords(chunks) if keyword not in answer_lower
        ]
        target = missing_keywords[0] if missing_keywords else "关键技术取舍"
        follow_up = (
            f"你刚才回答了“{question[:40]}”，请继续说明 {target} 在这个项目里的"
            "具体实现细节、失败场景以及你会如何验证它是可靠的。"
        )
        reason = "mock provider 根据回答中尚未充分覆盖的简历关键词生成追问"
        return follow_up, reason

    async def generate_live_interview_turn(
        self,
        system_prompt: str,
        turn_prompt: str,
        chunks: Sequence[InterviewSourceChunk],
        *,
        opening: bool,
        ask_next_question: bool,
    ) -> LiveInterviewTurn:
        del system_prompt, turn_prompt
        chunk = chunks[0]
        keywords = _keywords_or_defaults(chunk)
        if opening:
            return LiveInterviewTurn(
                greeting="你好，很高兴和你进行这场模拟面试。我们会围绕你的真实项目经历展开，请尽量结合具体细节作答。",
                question=(
                    f"先从简历中的 {', '.join(keywords[:2])} 经历谈起：你在这个项目里"
                    "承担了什么角色，最重要的目标是什么？"
                ),
                expected_points=["项目背景与个人职责", "关键目标或结果"],
                source_chunk_indexes=[chunk.chunk_index],
            )
        if not ask_next_question:
            return LiveInterviewTurn(
                feedback="谢谢你的回答。这场面试的主要问题已经完成，稍后我会为你汇总表现和下一步练习建议。",
                should_end=True,
            )
        return LiveInterviewTurn(
            feedback="我理解了你的思路。接下来我想进一步了解其中的关键决策。",
            question=(
                f"围绕 {keywords[0]}，你当时遇到过什么具体挑战？请说明你的判断、"
                "实现过程，以及如何验证结果。"
            ),
            expected_points=["具体挑战", "技术取舍", "验证与复盘"],
            source_chunk_indexes=[chunk.chunk_index],
        )

    async def stream_live_interview_turn(
        self,
        system_prompt: str,
        turn_prompt: str,
        chunks: Sequence[InterviewSourceChunk],
        *,
        opening: bool,
        ask_next_question: bool,
    ) -> AsyncIterator[str]:
        turn = await self.generate_live_interview_turn(
            system_prompt,
            turn_prompt,
            chunks,
            opening=opening,
            ask_next_question=ask_next_question,
        )
        payload = turn.model_dump_json()
        for index in range(0, len(payload), 12):
            yield payload[index : index + 12]


class OpenAICompatibleLLMProvider:
    name = "deepseek"

    def __init__(self) -> None:
        if not settings.LLM_API_KEY:
            raise provider_configuration_error("LLM_API_KEY is required for DeepSeek")
        self.client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=settings.LLM_MAX_RETRIES,
        )
        self.model = settings.LLM_MODEL_NAME

    async def generate_questions(
        self,
        prompt: str,
        focus: str,
        question_count: int,
        chunks: Sequence[InterviewSourceChunk],
    ) -> list[InterviewQuestion]:
        data = await self._json_chat(
            build_question_json_instruction(question_count, chunks),
            prompt,
        )
        return normalize_questions(data, focus, question_count, chunks)

    async def score_answer(
        self,
        prompt: str,
        question: str,
        answer: str,
        chunks: Sequence[InterviewSourceChunk],
    ) -> tuple[int, str, list[str], list[str], list[str]]:
        del question, answer
        data = await self._json_chat(build_score_json_instruction(), prompt)
        return normalize_score(data, chunks)

    async def generate_follow_up(
        self,
        prompt: str,
        question: str,
        answer: str,
        chunks: Sequence[InterviewSourceChunk],
    ) -> tuple[str, str]:
        del question, answer
        data = await self._json_chat(build_follow_up_json_instruction(), prompt)
        return normalize_follow_up(data, chunks)

    async def generate_live_interview_turn(
        self,
        system_prompt: str,
        turn_prompt: str,
        chunks: Sequence[InterviewSourceChunk],
        *,
        opening: bool,
        ask_next_question: bool,
    ) -> LiveInterviewTurn:
        del opening, ask_next_question
        data = await self._json_chat(system_prompt, turn_prompt)
        return normalize_live_interview_turn(data, chunks)

    async def stream_live_interview_turn(
        self,
        system_prompt: str,
        turn_prompt: str,
        chunks: Sequence[InterviewSourceChunk],
        *,
        opening: bool,
        ask_next_question: bool,
    ) -> AsyncIterator[str]:
        del chunks, opening, ask_next_question
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": turn_prompt},
                ],
                temperature=settings.LLM_TEMPERATURE,
                response_format={"type": "json_object"},
                stream=True,
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content if chunk.choices else None
                if content:
                    yield content
        except (APIError, APITimeoutError) as exc:
            raise provider_runtime_error("LLM provider request failed") from exc

    async def _json_chat(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=settings.LLM_TEMPERATURE,
                response_format={"type": "json_object"},
            )
        except (APIError, APITimeoutError) as exc:
            raise provider_runtime_error("LLM provider request failed") from exc

        content = response.choices[0].message.content if response.choices else ""
        return parse_json_object(content or "")


class OllamaLLMProvider:
    name = "ollama"

    def __init__(self) -> None:
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = settings.OLLAMA_MODEL_NAME

    async def generate_questions(
        self,
        prompt: str,
        focus: str,
        question_count: int,
        chunks: Sequence[InterviewSourceChunk],
    ) -> list[InterviewQuestion]:
        data = await self._json_chat(
            build_question_json_instruction(question_count, chunks),
            prompt,
        )
        return normalize_questions(data, focus, question_count, chunks)

    async def score_answer(
        self,
        prompt: str,
        question: str,
        answer: str,
        chunks: Sequence[InterviewSourceChunk],
    ) -> tuple[int, str, list[str], list[str], list[str]]:
        del question, answer
        data = await self._json_chat(build_score_json_instruction(), prompt)
        return normalize_score(data, chunks)

    async def generate_follow_up(
        self,
        prompt: str,
        question: str,
        answer: str,
        chunks: Sequence[InterviewSourceChunk],
    ) -> tuple[str, str]:
        del question, answer
        data = await self._json_chat(build_follow_up_json_instruction(), prompt)
        return normalize_follow_up(data, chunks)

    async def generate_live_interview_turn(
        self,
        system_prompt: str,
        turn_prompt: str,
        chunks: Sequence[InterviewSourceChunk],
        *,
        opening: bool,
        ask_next_question: bool,
    ) -> LiveInterviewTurn:
        del opening, ask_next_question
        data = await self._json_chat(system_prompt, turn_prompt)
        return normalize_live_interview_turn(data, chunks)

    async def stream_live_interview_turn(
        self,
        system_prompt: str,
        turn_prompt: str,
        chunks: Sequence[InterviewSourceChunk],
        *,
        opening: bool,
        ask_next_question: bool,
    ) -> AsyncIterator[str]:
        del chunks, opening, ask_next_question
        payload = {
            "model": self.model,
            "stream": True,
            "format": "json",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": turn_prompt},
            ],
            "options": {"temperature": settings.LLM_TEMPERATURE},
        }
        try:
            async with httpx.AsyncClient(
                timeout=settings.LLM_TIMEOUT_SECONDS,
                trust_env=False,
            ) as client:
                async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        content = json.loads(line).get("message", {}).get("content", "")
                        if content:
                            yield str(content)
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise provider_runtime_error("Ollama streaming request failed") from exc

    async def _json_chat(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {"temperature": settings.LLM_TEMPERATURE},
        }
        try:
            async with httpx.AsyncClient(
                timeout=settings.LLM_TIMEOUT_SECONDS,
                trust_env=False,
            ) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise provider_runtime_error("Ollama request failed") from exc

        data = response.json()
        content = data.get("message", {}).get("content", "")
        return parse_json_object(str(content))


class FallbackLLMProvider:
    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        self.primary = primary
        self.fallback = fallback
        self.name = f"{primary.name}+fallback"

    async def generate_questions(
        self,
        prompt: str,
        focus: str,
        question_count: int,
        chunks: Sequence[InterviewSourceChunk],
    ) -> list[InterviewQuestion]:
        return await self._call(
            lambda provider: provider.generate_questions(
                prompt,
                focus,
                question_count,
                chunks,
            )
        )

    async def score_answer(
        self,
        prompt: str,
        question: str,
        answer: str,
        chunks: Sequence[InterviewSourceChunk],
    ) -> tuple[int, str, list[str], list[str], list[str]]:
        return await self._call(
            lambda provider: provider.score_answer(prompt, question, answer, chunks)
        )

    async def generate_follow_up(
        self,
        prompt: str,
        question: str,
        answer: str,
        chunks: Sequence[InterviewSourceChunk],
    ) -> tuple[str, str]:
        return await self._call(
            lambda provider: provider.generate_follow_up(prompt, question, answer, chunks)
        )

    async def generate_live_interview_turn(
        self,
        system_prompt: str,
        turn_prompt: str,
        chunks: Sequence[InterviewSourceChunk],
        *,
        opening: bool,
        ask_next_question: bool,
    ) -> LiveInterviewTurn:
        return await self._call(
            lambda provider: provider.generate_live_interview_turn(
                system_prompt,
                turn_prompt,
                chunks,
                opening=opening,
                ask_next_question=ask_next_question,
            )
        )

    async def stream_live_interview_turn(
        self,
        system_prompt: str,
        turn_prompt: str,
        chunks: Sequence[InterviewSourceChunk],
        *,
        opening: bool,
        ask_next_question: bool,
    ) -> AsyncIterator[str]:
        try:
            async for token in self.primary.stream_live_interview_turn(
                system_prompt,
                turn_prompt,
                chunks,
                opening=opening,
                ask_next_question=ask_next_question,
            ):
                yield token
        except HTTPException:
            async for token in self.fallback.stream_live_interview_turn(
                system_prompt,
                turn_prompt,
                chunks,
                opening=opening,
                ask_next_question=ask_next_question,
            ):
                yield token

    async def _call(self, fn: Callable[[LLMProvider], Awaitable[Any]]) -> Any:
        try:
            return await fn(self.primary)
        except HTTPException:
            return await fn(self.fallback)


def get_llm_provider() -> LLMProvider:
    provider_name = settings.LLM_PROVIDER.strip().lower()
    if provider_name == "mock":
        return MockLLMProvider()

    try:
        if provider_name in {"deepseek", "openai-compatible", "openai_compatible"}:
            provider: LLMProvider = OpenAICompatibleLLMProvider()
        elif provider_name == "ollama":
            provider = OllamaLLMProvider()
        else:
            raise provider_configuration_error(
                f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER}"
            )
    except HTTPException:
        if settings.LLM_FALLBACK_TO_MOCK:
            return MockLLMProvider()
        raise

    if settings.LLM_FALLBACK_TO_MOCK:
        return FallbackLLMProvider(provider, MockLLMProvider())
    return provider


def build_question_json_instruction(
    question_count: int,
    chunks: Sequence[InterviewSourceChunk],
) -> str:
    indexes = [chunk.chunk_index for chunk in chunks]
    return (
        "You are an interview question generator. Return only valid JSON. "
        "Do not use markdown. The JSON object must have a `questions` array. "
        "Each item must include: difficulty (`easy`, `medium`, or `hard`), "
        "question, expected_points array, and source_chunk_indexes array. "
        f"Return exactly {question_count} questions. Allowed source_chunk_indexes: {indexes}."
    )


def build_score_json_instruction() -> str:
    return (
        "You are an interview answer evaluator. Return only valid JSON. "
        "Do not use markdown. The JSON object must include: score integer 0-100, "
        "level (`weak`, `basic`, `good`, or `strong`), strengths array, "
        "improvements array, and reference_points array."
    )


def build_follow_up_json_instruction() -> str:
    return (
        "You are an interview follow-up question generator. Return only valid JSON. "
        "Do not use markdown. The JSON object must include: follow_up_question and reason."
    )


def normalize_questions(
    data: dict[str, Any],
    focus: str,
    question_count: int,
    chunks: Sequence[InterviewSourceChunk],
) -> list[InterviewQuestion]:
    raw_questions = data.get("questions")
    if not isinstance(raw_questions, list):
        raise provider_parse_error("LLM response missing questions array")

    allowed_indexes = {chunk.chunk_index for chunk in chunks}
    questions: list[InterviewQuestion] = []
    for index, raw in enumerate(raw_questions[:question_count]):
        if not isinstance(raw, dict):
            continue
        difficulty = normalize_difficulty(raw.get("difficulty"), index)
        source_indexes = normalize_source_indexes(
            raw.get("source_chunk_indexes"),
            allowed_indexes,
            chunks[index % len(chunks)].chunk_index,
        )
        expected_points = normalize_string_list(
            raw.get("expected_points"),
            ["能结合简历片段说明实现背景", "能讲清技术选型和验证方式"],
        )
        question_text = str(raw.get("question") or "").strip()
        if not question_text:
            keywords = _keywords_or_defaults(chunks[index % len(chunks)])
            question_text = (
                f"结合你简历中关于 {', '.join(keywords[:3])} 的经历，说明你在 "
                f"{focus} 场景下是如何设计、实现并验证效果的？"
            )
        try:
            questions.append(
                InterviewQuestion(
                    question_id=str(raw.get("question_id") or f"llm-q-{index + 1}"),
                    difficulty=difficulty,
                    question=question_text,
                    expected_points=expected_points,
                    source_chunk_indexes=source_indexes,
                )
            )
        except ValidationError as exc:
            raise provider_parse_error("LLM question response failed validation") from exc

    if not questions:
        raise provider_parse_error("LLM response did not contain usable questions")
    return questions


def normalize_score(
    data: dict[str, Any],
    chunks: Sequence[InterviewSourceChunk],
) -> tuple[int, str, list[str], list[str], list[str]]:
    del chunks
    score = clamp_int(data.get("score"), 0, 100, default=60)
    level = normalize_level(data.get("level"), score)
    strengths = normalize_string_list(data.get("strengths"), ["回答和问题目标保持相关"])
    improvements = normalize_string_list(
        data.get("improvements"),
        ["补充更具体的实现细节、失败场景和验证方式"],
    )
    reference_points = normalize_string_list(
        data.get("reference_points"),
        ["建议结合简历片段补充证据"],
    )
    return score, level, strengths, improvements, reference_points


def normalize_follow_up(
    data: dict[str, Any],
    chunks: Sequence[InterviewSourceChunk],
) -> tuple[str, str]:
    fallback_target = _keywords_or_defaults(chunks[0])[0] if chunks else "关键技术取舍"
    question = str(data.get("follow_up_question") or "").strip()
    if not question:
        question = f"请继续说明 {fallback_target} 的实现细节、失败场景和验证方式。"
    reason = str(data.get("reason") or "").strip()
    if not reason:
        reason = "真实模型根据简历上下文和候选人回答生成追问"
    return question, reason


def normalize_live_interview_turn(
    data: dict[str, Any],
    chunks: Sequence[InterviewSourceChunk],
) -> LiveInterviewTurn:
    fallback_index = chunks[0].chunk_index if chunks else 0
    indexes = normalize_source_indexes(
        data.get("source_chunk_indexes"),
        {chunk.chunk_index for chunk in chunks},
        fallback_index,
    )
    question = str(data.get("question") or "").strip() or None
    greeting = str(data.get("greeting") or "").strip() or None
    feedback = str(data.get("feedback") or "").strip() or None
    if question is None and feedback is None and greeting is None:
        raise provider_parse_error("LLM live interview response was empty")
    return LiveInterviewTurn(
        greeting=greeting,
        feedback=feedback,
        question=question,
        expected_points=normalize_string_list(
            data.get("expected_points"),
            ["结合真实项目说明背景、实现和验证"],
        ),
        source_chunk_indexes=indexes if question is not None else [],
        should_end=data.get("should_end") is True
        or str(data.get("should_end", "")).strip().lower() == "true",
    )


def normalize_difficulty(value: Any, index: int) -> Difficulty:
    if value in {"easy", "medium", "hard"}:
        return value
    fallback: list[Difficulty] = ["easy", "medium", "hard"]
    return fallback[min(index, len(fallback) - 1)]


def normalize_level(value: Any, score: int) -> ScoreLevel:
    if value in {"weak", "basic", "good", "strong"}:
        return value
    if score >= 85:
        return "strong"
    if score >= 70:
        return "good"
    if score >= 55:
        return "basic"
    return "weak"


def normalize_source_indexes(
    value: Any,
    allowed_indexes: set[int],
    fallback_index: int,
) -> list[int]:
    if not isinstance(value, list):
        return [fallback_index]
    indexes: list[int] = []
    for item in value:
        try:
            index = int(item)
        except (TypeError, ValueError):
            continue
        if index in allowed_indexes and index not in indexes:
            indexes.append(index)
    return indexes or [fallback_index]


def normalize_string_list(value: Any, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return fallback
    items = [str(item).strip() for item in value if str(item).strip()]
    return items[:8] or fallback


def clamp_int(value: Any, minimum: int, maximum: int, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(number, maximum))


def parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    if not text:
        raise provider_parse_error("LLM response was empty")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise provider_parse_error("LLM response did not contain JSON")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise provider_parse_error("LLM response JSON could not be parsed") from exc
    if not isinstance(data, dict):
        raise provider_parse_error("LLM response JSON must be an object")
    return data


def provider_configuration_error(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"LLM provider is not configured: {detail}",
    )


def provider_runtime_error(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=detail,
    )


def provider_parse_error(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=detail,
    )


def _keywords_or_defaults(chunk: InterviewSourceChunk) -> list[str]:
    keywords = [keyword for keyword in chunk.keywords if keyword]
    return keywords[:3] or ["项目背景", "技术实现", "问题排查"]


def _unique_keywords(chunks: Sequence[InterviewSourceChunk]) -> list[str]:
    seen: set[str] = set()
    keywords: list[str] = []
    for chunk in chunks:
        for keyword in chunk.keywords:
            normalized = keyword.lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                keywords.append(normalized)
    return keywords[:12]
