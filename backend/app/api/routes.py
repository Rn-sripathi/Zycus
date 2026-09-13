"""HTTP routes. Thin: parse, delegate to the pipeline, serialise."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.config import DATA_DIR, get_settings
from app.api.schemas import (
    HealthResponse,
    ReviewRequest,
    ReviewResponse,
    RuleOut,
    SamplesResponse,
)
from app.domain.playbook import PLAYBOOK
from app.llm.client import LLMClient, LLMError
from app.pipeline.orchestrator import review_contract

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        llm_configured=settings.llm_enabled,
        model=settings.openai_model,
    )


@router.get("/playbook", response_model=list[RuleOut])
async def get_playbook() -> list[RuleOut]:
    return [RuleOut.from_domain(rule) for rule in PLAYBOOK]


@router.get("/samples", response_model=SamplesResponse)
async def get_samples() -> SamplesResponse:
    return SamplesResponse(
        sample_contract=_read("sample_contract.txt"),
        ambiguous_contract=_read("ambiguous_clause.txt"),
    )


@router.post("/review", response_model=ReviewResponse)
async def review(request: ReviewRequest) -> ReviewResponse:
    settings = get_settings()
    if not settings.llm_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured on the server.",
        )

    try:
        client = LLMClient()
        result = await review_contract(request.contract_text, client)
    except LLMError as exc:
        logger.exception("Review failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"The review could not be completed: {exc}",
        ) from exc

    if not result.findings and result.summary.clauses_reviewed == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "No numbered clauses were found. Clauses should start on a new line, "
                'for example "1. Term and Termination. ..."'
            ),
        )

    return ReviewResponse.from_domain(result)


def _read(filename: str) -> str:
    return (DATA_DIR / filename).read_text(encoding="utf-8")
