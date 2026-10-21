from typing import Any

from app.services.validation import AnswerValidationError, validate_answer


class PathValidationError(ValueError):
    def __init__(self, code: str, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def rule_matches(question_type: str, answer: Any, rule: dict[str, Any]) -> bool:
    operator = rule["operator"]
    expected = rule["value"]
    if question_type == "single_choice":
        return operator == "eq" and answer == expected
    if question_type == "multiple_choice":
        selected = set(answer)
        expected_set = set(expected)
        if operator == "contains_any":
            return bool(selected & expected_set)
        if operator == "contains_all":
            return expected_set <= selected
        return False
    if question_type == "number":
        return {
            "eq": answer == expected,
            "gt": answer > expected,
            "gte": answer >= expected,
            "lt": answer < expected,
            "lte": answer <= expected,
        }.get(operator, False)
    return False


def next_question_index(
    questions: list[dict[str, Any]], current_index: int, answer_present: bool, answer: Any
) -> int:
    if answer_present:
        question = questions[current_index]
        for rule in sorted(question.get("rules", []), key=lambda item: item["priority"]):
            if rule_matches(question["type"], answer, rule):
                positions = {item["id"]: index for index, item in enumerate(questions)}
                return positions[rule["target_question_id"]]
    return current_index + 1


def replay_path(
    questions: list[dict[str, Any]], submitted_answers: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    submitted_ids = [answer["question_id"] for answer in submitted_answers]
    duplicates = sorted({item for item in submitted_ids if submitted_ids.count(item) > 1})
    if duplicates:
        raise PathValidationError("DUPLICATE_QUESTION", "同一道题不能提交多份答案", duplicates)

    question_ids = {question["id"] for question in questions}
    unknown = sorted(set(submitted_ids) - question_ids)
    if unknown:
        raise PathValidationError("UNKNOWN_QUESTION", "提交包含未知题目", unknown)

    answer_map = {answer["question_id"]: answer["value"] for answer in submitted_answers}
    visited: list[str] = []
    visited_set: set[str] = set()
    normalized: list[dict[str, Any]] = []
    index = 0
    while index < len(questions):
        question = questions[index]
        question_id = question["id"]
        if question_id in visited_set:
            raise PathValidationError("INVALID_RULE_GRAPH", "问卷规则产生了循环")
        visited.append(question_id)
        visited_set.add(question_id)
        try:
            result = validate_answer(
                question,
                answer_map.get(question_id),
                question_id in answer_map,
            )
        except AnswerValidationError as error:
            raise PathValidationError(
                "INVALID_ANSWER",
                error.message,
                {"question_id": error.question_id},
            ) from error
        if result.present:
            normalized.append({"question_id": question_id, "value": result.value})
        next_index = next_question_index(questions, index, result.present, result.value)
        if next_index <= index:
            raise PathValidationError("INVALID_RULE_GRAPH", "问卷规则必须向后跳转")
        index = next_index

    outside_path = sorted(set(submitted_ids) - visited_set)
    if outside_path:
        raise PathValidationError(
            "ANSWER_OUTSIDE_PATH",
            "提交包含实际访问路径之外的题目答案",
            outside_path,
        )
    return normalized, visited
