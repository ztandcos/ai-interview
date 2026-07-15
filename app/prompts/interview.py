from collections.abc import Sequence

from app.schemas.interview import InterviewSourceChunk


def format_chunks_for_prompt(chunks: Sequence[InterviewSourceChunk]) -> str:
    lines: list[str] = []
    for chunk in chunks:
        keywords = ", ".join(chunk.keywords[:8]) or "none"
        lines.append(
            "\n".join(
                [
                    f"[chunk #{chunk.chunk_index}, score={chunk.score}]",
                    f"keywords: {keywords}",
                    f"content: {chunk.content}",
                ]
            )
        )
    return "\n\n".join(lines)


def build_question_generation_prompt(
    focus: str,
    question_count: int,
    chunks: Sequence[InterviewSourceChunk],
) -> str:
    return "\n\n".join(
        [
            "You are an AI interview coach.",
            "Generate resume-grounded interview questions from the retrieved chunks.",
            "Return structured questions with difficulty, expected points, and chunk references.",
            f"Focus: {focus}",
            f"Question count: {question_count}",
            "Retrieved chunks:",
            format_chunks_for_prompt(chunks),
        ]
    )


def build_answer_scoring_prompt(
    question: str,
    answer: str,
    chunks: Sequence[InterviewSourceChunk],
) -> str:
    return "\n\n".join(
        [
            "You are an AI interview evaluator.",
            "Score the candidate answer using only the retrieved resume chunks as references.",
            "Return a structured score, strengths, improvements, and reference points.",
            f"Question: {question}",
            f"Answer: {answer}",
            "Retrieved chunks:",
            format_chunks_for_prompt(chunks),
        ]
    )


def build_follow_up_prompt(
    question: str,
    answer: str,
    chunks: Sequence[InterviewSourceChunk],
) -> str:
    return "\n\n".join(
        [
            "You are an AI interviewer.",
            "Ask one follow-up question based on the candidate answer and resume chunks.",
            "The follow-up should test implementation detail, tradeoff, or debugging ability.",
            f"Original question: {question}",
            f"Candidate answer: {answer}",
            "Retrieved chunks:",
            format_chunks_for_prompt(chunks),
        ]
    )
