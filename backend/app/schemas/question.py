from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.survey import OptionInput, QuestionType


class QuestionContentInput(BaseModel):
    type: QuestionType
    title: str = Field(min_length=1, max_length=500)
    options: list[OptionInput] = Field(default_factory=list, max_length=100)
    validation: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("题目标题不能为空")
        return value


class QuestionCreate(QuestionContentInput):
    change_note: str = Field(default="创建题目", max_length=500)


class QuestionVersionCreate(QuestionContentInput):
    parent_version_id: str | None = None
    change_note: str = Field(default="", max_length=500)


class QuestionShareCreate(BaseModel):
    username: str = Field(min_length=3, max_length=32)


class QuestionBankCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("题库名称不能为空")
        return value


class QuestionBankUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("题库名称不能为空")
        return value


class QuestionBankItemCreate(BaseModel):
    question_id: str
    default_version_id: str | None = None


class QuestionBankItemUpdate(BaseModel):
    default_version_id: str


class LibraryQuestionUse(BaseModel):
    question_id: str
    question_version_id: str | None = None
    required: bool = False


class SurveyQuestionVersionSwitch(BaseModel):
    question_version_id: str
