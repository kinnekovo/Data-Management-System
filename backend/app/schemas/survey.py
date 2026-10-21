from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

QuestionType = Literal["single_choice", "multiple_choice", "text", "number"]
SurveyStatus = Literal["draft", "published", "closed"]


class OptionInput(BaseModel):
    id: str | None = Field(default=None, min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=200)

    @field_validator("label")
    @classmethod
    def label_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("选项标题不能为空")
        return value


class RuleInput(BaseModel):
    priority: int = Field(ge=0, le=10000)
    operator: str = Field(min_length=1, max_length=30)
    value: Any
    target_question_id: str = Field(min_length=1, max_length=80)


class QuestionInput(BaseModel):
    type: QuestionType
    title: str = Field(min_length=1, max_length=500)
    required: bool = False
    options: list[OptionInput] = Field(default_factory=list, max_length=100)
    validation: dict[str, Any] = Field(default_factory=dict)
    rules: list[RuleInput] = Field(default_factory=list, max_length=100)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("题目标题不能为空")
        return value


class SurveyCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    allow_anonymous: bool = False
    allow_multiple_submissions: bool = False
    expires_at: datetime | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("问卷标题不能为空")
        return value


class SurveyUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    allow_anonymous: bool | None = None
    allow_multiple_submissions: bool | None = None
    expires_at: datetime | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("问卷标题不能为空")
        return value


class QuestionOrderUpdate(BaseModel):
    question_ids: list[str] = Field(min_length=1, max_length=200)


class SurveyView(BaseModel):
    id: str
    slug: str
    title: str
    description: str
    allow_anonymous: bool
    allow_multiple_submissions: bool
    status: SurveyStatus
    expires_at: str | None
    questions: list[dict[str, Any]]
    schema_version: int
    definition_version: int
    created_at: str
    updated_at: str
    published_at: str | None
    closed_at: str | None
