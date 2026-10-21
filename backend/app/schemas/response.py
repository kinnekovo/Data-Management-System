from typing import Any

from pydantic import BaseModel, Field


class AnswerInput(BaseModel):
    question_id: str = Field(min_length=1, max_length=80)
    value: Any


class SubmissionInput(BaseModel):
    answers: list[AnswerInput] = Field(default_factory=list, max_length=500)
