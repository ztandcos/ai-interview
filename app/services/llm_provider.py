from collections.abc import Sequence
from typing import Protocol

from app.core.config import settings
from app.schemas.interview import InterviewQuestion, InterviewSourceChunk


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
        difficulties = ["easy", "medium", "hard"]
        questions: list[InterviewQuestion] = []
        for index in range(question_count):
            chunk = chunks[index % len(chunks)]
            keywords = _keywords_or_defaults(chunk)
            keyword_text = ", ".join(keywords[:3])
            difficulty = difficulties[min(index, len(difficulties) - 1)]
            questions.append(
                InterviewQuestion(
                    question_id=f"mock-q-{index + 1}",
                    difficulty=difficulty,  # type: ignore[arg-type]
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


def get_llm_provider() -> LLMProvider:
    if settings.LLM_PROVIDER.strip().lower() != "mock":
        raise ValueError("Only the mock LLM provider is supported in this stage")
    return MockLLMProvider()


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
