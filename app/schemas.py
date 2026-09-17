from datetime import datetime

from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    code: str = Field(min_length=1, max_length=100_000)


class ReviewResponse(BaseModel):
    id: int
    score: int
    syntax: dict
    complexity: dict
    issues: list[dict]
    summary: str = ""
    recommendations: list[str] = Field(default_factory=list)
    metrics: dict
    created_at: datetime


class HistoryItem(BaseModel):
    id: int
    score: int
    complexity: str
    issue_count: int
    created_at: datetime
