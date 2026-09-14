"""HTTP routes. Thin: parse, delegate to the pipeline, serialise."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.schemas import (
    HealthResponse,
    ReviewHistoryItem,
    ReviewRequest,
    ReviewResponse,
    RuleOut,
    SamplesResponse,
)
from app.config import DATA_DIR, get_settings
from app.domain.playbook import PLAYBOOK
from app.llm.client import LLMClient, LLMError
from app.orchestrator import review_contract
from app.storage import db
from app.storage import reviews as review_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        llm_configured=settings.llm_enabled,
        persistence_enabled=db.is_enabled(),
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
async def review(request: ReviewRequest, label: str = Query("")) -> ReviewResponse:
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

    # Best-effort: a storage failure must not cost the reviewer their findings.
    review_id = await review_store.save_review(
        result,
        request.contract_text,
        label=label,
        model=settings.openai_model,
    )

    return ReviewResponse.from_domain(result, review_id=str(review_id) if review_id else None)


@router.get("/reviews", response_model=list[ReviewHistoryItem])
async def list_reviews(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[ReviewHistoryItem]:
    """Past reviews, newest first. Empty when persistence is disabled."""
    stored = await review_store.list_reviews(limit=limit, offset=offset)
    return [ReviewHistoryItem.from_domain(item) for item in stored]


@router.get("/reviews/{review_id}", response_model=ReviewResponse)
async def get_review(review_id: str) -> ReviewResponse:
    """Reload a stored review, including the contract it ran against."""
    found = await review_store.get_review(_as_uuid(review_id))
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No stored review with that id.",
        )

    result, contract_text = found
    return ReviewResponse.from_domain(
        result, review_id=review_id, contract_text=contract_text
    )


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(review_id: str) -> None:
    if not await review_store.delete_review(_as_uuid(review_id)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No stored review with that id.",
        )


def _as_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review id must be a UUID.",
        ) from exc


def _read(filename: str) -> str:
    return (DATA_DIR / filename).read_text(encoding="utf-8")
