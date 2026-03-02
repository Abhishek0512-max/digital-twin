from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ChatMessage(BaseModel):
    role: str
    content: str


class FeedbackRating(str, Enum):
    UP = "up"
    DOWN = "down"


class FeedbackRequest(BaseModel):
    message_id: str
    conversation_id: str
    question: str
    response: str
    rating: FeedbackRating
    comment: Optional[str] = None


class Chunk(BaseModel):
    text: str
    source: str
    section: str = ""
    score: float = 0.0


class EvalResult(BaseModel):
    question: str
    expected_answer: str
    actual_answer: str
    retrieved_chunks: list[str] = Field(default_factory=list)
    faithfulness: float = 0.0
    relevance: float = 0.0
    persona: float = 0.0
    overall: float = 0.0
    judge_reasoning: str = ""
