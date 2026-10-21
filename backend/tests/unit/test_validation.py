import math

import pytest

from app.services.rule_engine import PathValidationError, replay_path, rule_matches
from app.services.validation import AnswerValidationError, validate_answer, validate_survey_definition


def option(identifier):
    return {"id": identifier, "label": identifier.upper()}


def question(identifier, kind, *, required=False, options=None, validation=None, rules=None):
    return {
        "id": identifier,
        "type": kind,
        "title": identifier,
        "required": required,
        "options": options or [],
        "validation": validation or {},
        "rules": rules or [],
    }


@pytest.mark.parametrize(
    ("kind", "answer", "operator", "expected", "matches"),
    [
        ("single_choice", "a", "eq", "a", True),
        ("multiple_choice", ["a", "b"], "contains_any", ["b", "c"], True),
        ("multiple_choice", ["a", "b"], "contains_all", ["a", "b"], True),
        ("multiple_choice", ["a"], "contains_all", ["a", "b"], False),
        ("number", 10, "eq", 10, True),
        ("number", 10, "gt", 10, False),
        ("number", 10, "gte", 10, True),
        ("number", 10, "lt", 11, True),
        ("number", 10, "lte", 10, True),
    ],
)
def test_rule_operators(kind, answer, operator, expected, matches):
    assert rule_matches(kind, answer, {"operator": operator, "value": expected}) is matches


def test_definition_rejects_missing_and_invalid_rules():
    assert validate_survey_definition([])[0]["field"] == "questions"
    questions = [
        question(
            "q1",
            "single_choice",
            options=[option("a"), option("b")],
            rules=[
                {"priority": 1, "operator": "eq", "value": "a", "target_question_id": "missing"},
                {"priority": 1, "operator": "eq", "value": "x", "target_question_id": "q1"},
            ],
        ),
        question("q2", "text"),
    ]
    messages = [item["message"] for item in validate_survey_definition(questions)]
    assert any("优先级" in message for message in messages)
    assert any("目标题不存在" in message for message in messages)
    assert any("向后跳转" in message for message in messages)
    assert any("属于本题选项" in message for message in messages)


@pytest.mark.parametrize(
    ("question_data", "answer", "message"),
    [
        (question("q", "single_choice", options=[option("a"), option("b")]), "x", "合法选项"),
        (question("q", "multiple_choice", options=[option("a"), option("b")]), ["a", "a"], "重复"),
        (question("q", "multiple_choice", options=[option("a"), option("b")]), ["x"], "未知选项"),
        (question("q", "multiple_choice", options=[option("a"), option("b")], validation={"min_selections": 2}), ["a"], "至少"),
        (question("q", "multiple_choice", options=[option("a"), option("b")], validation={"max_selections": 1}), ["a", "b"], "最多"),
        (question("q", "text", validation={"min_length": 3}), "ab", "不能少于"),
        (question("q", "text", required=True), "   ", "必答"),
        (question("q", "text", validation={"max_length": 2}), "abc", "不能超过"),
        (question("q", "number"), "12", "JSON 数字"),
        (question("q", "number"), True, "JSON 数字"),
        (question("q", "number", validation={"integer_only": True}), 1.5, "整数"),
        (question("q", "number", validation={"min_value": 2}), 1, "不能小于"),
        (question("q", "number", validation={"max_value": 2}), 3, "不能大于"),
    ],
)
def test_answer_validation_boundaries(question_data, answer, message):
    with pytest.raises(AnswerValidationError, match=message):
        validate_answer(question_data, answer, True)


@pytest.mark.parametrize("bad_number", [math.nan, math.inf, -math.inf])
def test_number_rejects_non_finite_values(bad_number):
    with pytest.raises(AnswerValidationError, match="有限"):
        validate_answer(question("q", "number"), bad_number, True)


def test_replay_path_skips_required_question_and_rejects_answer_outside_path():
    questions = [
        question(
            "q1",
            "single_choice",
            required=True,
            options=[option("skip"), option("continue")],
            rules=[{"priority": 1, "operator": "eq", "value": "skip", "target_question_id": "q3"}],
        ),
        question("q2", "text", required=True),
        question("q3", "number", required=True, validation={"integer_only": True}),
    ]
    normalized, visited = replay_path(
        questions,
        [{"question_id": "q1", "value": "skip"}, {"question_id": "q3", "value": 7}],
    )
    assert visited == ["q1", "q3"]
    assert [item["question_id"] for item in normalized] == ["q1", "q3"]

    with pytest.raises(PathValidationError) as error:
        replay_path(
            questions,
            [
                {"question_id": "q1", "value": "skip"},
                {"question_id": "q2", "value": "forged"},
                {"question_id": "q3", "value": 7},
            ],
        )
    assert error.value.code == "ANSWER_OUTSIDE_PATH"


def test_replay_path_rejects_duplicate_and_unknown_question_ids():
    questions = [question("q1", "text")]
    with pytest.raises(PathValidationError) as duplicate:
        replay_path(questions, [{"question_id": "q1", "value": "a"}, {"question_id": "q1", "value": "b"}])
    assert duplicate.value.code == "DUPLICATE_QUESTION"
    with pytest.raises(PathValidationError) as unknown:
        replay_path(questions, [{"question_id": "missing", "value": "a"}])
    assert unknown.value.code == "UNKNOWN_QUESTION"


def test_optional_unanswered_question_does_not_trigger_rule():
    questions = [
        question(
            "q1",
            "number",
            rules=[{"priority": 1, "operator": "gt", "value": 0, "target_question_id": "q3"}],
        ),
        question("q2", "text", required=True),
        question("q3", "text"),
    ]
    _, visited = replay_path(questions, [{"question_id": "q2", "value": "顺序到达"}])
    assert visited == ["q1", "q2", "q3"]
