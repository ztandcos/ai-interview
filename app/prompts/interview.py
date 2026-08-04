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


def build_live_interview_system_prompt(difficulty: str) -> str:
    difficulty_instructions = {
        "easy": (
            "Use a friendly, reassuring tone. Start from project background, personal role, "
            "and core concepts. Give one small clarification when the candidate is stuck."
        ),
        "medium": (
            "Probe implementation detail, trade-offs, debugging, testing, and measurable "
            "outcomes. Keep the tone professional and encouraging."
        ),
        "hard": (
            "Probe system design, constraints, failure modes, scalability, security, and "
            "alternatives. Challenge unsupported claims while staying respectful."
        ),
    }
    return "\n\n".join(
        [
            "You are a senior interviewer conducting a live Chinese interview.",
            "Do not reveal internal rubrics or say that you are an AI.",
            "Ask exactly one focused question at a time. Adapt the next question to the "
            "candidate's answer instead of following a fixed question list.",
            "Ground questions in the retrieved resume evidence; do not invent experience.",
            difficulty_instructions.get(difficulty, difficulty_instructions["medium"]),
        ]
    )


def build_live_interview_turn_prompt(
    *,
    focus: str,
    difficulty: str,
    turn_number: int,
    history: str,
    chunks: Sequence[InterviewSourceChunk],
    opening: bool,
    ask_next_question: bool,
) -> str:
    stage = (
        "This is the opening. Give a short natural greeting (one or two sentences), then ask "
        "the first resume-grounded question."
        if opening
        else (
            "Briefly acknowledge the last answer and ask the next best question."
            if ask_next_question
            else "Briefly close the conversation after the last answer; do not ask another question."
        )
    )
    return "\n\n".join(
        [
            "Return only valid JSON. Do not use markdown.",
            "JSON keys: greeting (string or null), feedback (string or null), question "
            "(string or null), expected_points (string array), source_chunk_indexes (integer array).",
            f"Target role: {focus}",
            f"Difficulty: {difficulty}",
            f"Question number: {turn_number}",
            f"Instruction: {stage}",
            "Conversation so far:",
            history or "No prior messages.",
            "Retrieved resume chunks:",
            format_chunks_for_prompt(chunks),
        ]
    )
