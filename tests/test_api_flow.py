from __future__ import annotations

import time
from typing import Any

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


SAMPLE_RESUME_TEXT = """
AI Interview Copilot 项目使用 FastAPI 构建后端接口，使用 MySQL 保存用户、简历、
resume chunks、interview messages 和 interview reports。项目用 Redis 实现验证码
和登录限流，用 JWT access token 与 refresh token 维护登录态。简历上传后，后端使用
pypdf 提取 PDF 文本，再按 chunk size 和 overlap 切分简历文本。RAG 第一版使用
关键词检索：从用户问题和简历 chunk 中抽取 FastAPI、Redis、MySQL、RAG、LLM、
Ollama、DeepSeek 等关键词，然后给相关 chunk 打分。面试流程会先根据目标岗位生成
个性化问题，再保存用户回答，调用 LLM provider 评分并生成追问，最后汇总 score
messages 生成 interview report。项目强调接口、schema、service、model、database
之间的调用链路，并通过 Alembic 管理数据库迁移。
""" * 3


async def register_and_login(client: AsyncClient) -> dict[str, str]:
    email = f"api-test-{time.time_ns()}@example.com"
    password = "Password123456"

    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "API Test User",
        },
    )
    assert register_response.status_code == 201
    assert register_response.json()["email"] == email

    code_response = await client.post(
        "/api/v1/verification/send",
        json={"email": email},
    )
    assert code_response.status_code == 200
    code = code_response.json()["codes"]

    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password,
            "code": code,
        },
    )
    assert login_response.status_code == 200
    body = login_response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]

    return {
        "email": email,
        "password": password,
        "access_token": body["access_token"],
        "refresh_token": body["refresh_token"],
    }


def auth_headers(tokens: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_auth_register_login_refresh_me_logout(client: AsyncClient) -> None:
    tokens = await register_and_login(client)

    me_response = await client.get("/api/v1/auth/me", headers=auth_headers(tokens))
    assert me_response.status_code == 200
    assert me_response.json()["email"] == tokens["email"]

    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"]

    logout_response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert logout_response.status_code == 200
    assert logout_response.json() == {"message": "Logged out"}

    refresh_after_logout_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_after_logout_response.status_code == 401


async def test_protected_resume_endpoint_requires_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/resumes")

    assert response.status_code == 401


async def test_resume_rag_and_interview_session_flow(
    client: AsyncClient,
    monkeypatch: Any,
) -> None:
    from app.services import resume_service

    monkeypatch.setattr(
        resume_service,
        "extract_text_from_pdf",
        lambda _: SAMPLE_RESUME_TEXT,
    )

    tokens = await register_and_login(client)
    headers = auth_headers(tokens)

    upload_response = await client.post(
        "/api/v1/resumes",
        headers=headers,
        files={
            "file": (
                "resume.pdf",
                b"%PDF-1.4\n% test pdf bytes\n",
                "application/pdf",
            )
        },
    )
    assert upload_response.status_code == 201
    resume = upload_response.json()
    resume_id = resume["id"]
    assert resume["original_filename"] == "resume.pdf"
    assert resume["extracted_text_length"] == len(SAMPLE_RESUME_TEXT)

    list_response = await client.get("/api/v1/resumes", headers=headers)
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [resume_id]

    detail_response = await client.get(f"/api/v1/resumes/{resume_id}", headers=headers)
    assert detail_response.status_code == 200
    assert "FastAPI" in detail_response.json()["extracted_text"]

    build_response = await client.post(
        f"/api/v1/resumes/{resume_id}/chunks",
        headers=headers,
    )
    assert build_response.status_code == 200
    chunks_created = build_response.json()["chunks_created"]
    assert chunks_created > 1

    chunks_response = await client.get(
        f"/api/v1/resumes/{resume_id}/chunks",
        headers=headers,
    )
    assert chunks_response.status_code == 200
    assert len(chunks_response.json()) == chunks_created

    search_response = await client.post(
        f"/api/v1/resumes/{resume_id}/search",
        headers=headers,
        json={
            "query": "FastAPI Redis RAG 面试评分",
            "top_k": 3,
        },
    )
    assert search_response.status_code == 200
    search_results = search_response.json()
    assert search_results
    assert search_results[0]["score"] > 0

    question_response = await client.post(
        f"/api/v1/resumes/{resume_id}/interview/questions",
        headers=headers,
        json={
            "focus": "AI application backend intern",
            "question_count": 3,
            "top_k": 5,
        },
    )
    assert question_response.status_code == 200
    generated = question_response.json()
    assert generated["provider"] == "mock"
    assert len(generated["questions"]) == 3
    assert generated["source_chunks"]

    score_response = await client.post(
        f"/api/v1/resumes/{resume_id}/interview/score",
        headers=headers,
        json={
            "question": generated["questions"][0]["question"],
            "answer": (
                "我用 FastAPI 实现接口，用 Redis 做验证码和冷却限制，"
                "用 MySQL 保存简历和面试消息，并通过 RAG 检索 chunks 后调用 LLM 评分。"
                "我会通过接口测试验证上传、检索、生成题目和报告链路。"
            ),
            "top_k": 5,
        },
    )
    assert score_response.status_code == 200
    assert 0 <= score_response.json()["score"] <= 100

    follow_up_response = await client.post(
        f"/api/v1/resumes/{resume_id}/interview/follow-up",
        headers=headers,
        json={
            "question": generated["questions"][0]["question"],
            "answer": "我实现了 FastAPI、Redis、MySQL 和 RAG 相关链路。",
            "top_k": 5,
        },
    )
    assert follow_up_response.status_code == 200
    assert follow_up_response.json()["follow_up_question"]

    start_response = await client.post(
        "/api/v1/interviews",
        headers=headers,
        json={
            "resume_id": resume_id,
            "focus": "AI application backend intern",
            "question_count": 3,
            "top_k": 5,
        },
    )
    assert start_response.status_code == 200
    started = start_response.json()
    interview_id = started["interview"]["id"]
    question_message_ids = [
        message["id"]
        for message in started["messages"]
        if message["message_type"] == "question"
    ]
    assert started["interview"]["status"] == "active"
    assert len(question_message_ids) == 3

    answer_response = await client.post(
        f"/api/v1/interviews/{interview_id}/answers",
        headers=headers,
        json={
            "question_message_id": question_message_ids[0],
            "answer": (
                "这个项目的链路是上传 PDF 后提取文本，切成 chunks，"
                "再根据面试方向检索相关上下文，拼接 prompt 调用 mock 或真实 LLM。"
                "回答提交后会保存 answer、score 和 follow_up 三类消息。"
            ),
            "top_k": 5,
        },
    )
    assert answer_response.status_code == 200
    answer_body = answer_response.json()
    assert answer_body["answer_message"]["message_type"] == "answer"
    assert answer_body["score_message"]["message_type"] == "score"
    assert answer_body["follow_up_message"]["message_type"] == "follow_up"
    assert answer_body["score_message"]["score"] is not None

    detail_response = await client.get(
        f"/api/v1/interviews/{interview_id}",
        headers=headers,
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert len(detail["messages"]) == 6
    assert detail["report"] is None

    complete_response = await client.post(
        f"/api/v1/interviews/{interview_id}/complete",
        headers=headers,
    )
    assert complete_response.status_code == 200
    completed = complete_response.json()
    assert completed["interview"]["status"] == "completed"
    assert 0 <= completed["report"]["overall_score"] <= 100
    assert completed["report"]["suggestions"]

    interviews_response = await client.get("/api/v1/interviews", headers=headers)
    assert interviews_response.status_code == 200
    assert interviews_response.json()[0]["id"] == interview_id
