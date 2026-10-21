import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnswerResult:
    present: bool
    value: Any = None


class AnswerValidationError(ValueError):
    def __init__(self, question_id: str, message: str) -> None:
        super().__init__(message)
        self.question_id = question_id
        self.message = message


def _valid_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _empty_value(question_type: str, value: Any) -> bool:
    if value is None:
        return True
    if question_type == "text" and isinstance(value, str) and not value.strip():
        return True
    if question_type == "multiple_choice" and isinstance(value, list) and not value:
        return True
    return False


def validate_answer(question: dict[str, Any], value: Any, is_present: bool) -> AnswerResult:
    question_id = question["id"]
    question_type = question["type"]
    required = bool(question.get("required"))

    if not is_present or _empty_value(question_type, value):
        if required:
            raise AnswerValidationError(question_id, "该题为必答题")
        return AnswerResult(False)

    option_ids = {option["id"] for option in question.get("options", [])}
    validation = question.get("validation", {})

    if question_type == "single_choice":
        if not isinstance(value, str) or value not in option_ids:
            raise AnswerValidationError(question_id, "单选答案必须是该题的合法选项 ID")
        return AnswerResult(True, value)

    if question_type == "multiple_choice":
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise AnswerValidationError(question_id, "多选答案必须是选项 ID 数组")
        if len(value) != len(set(value)):
            raise AnswerValidationError(question_id, "多选答案不能包含重复选项")
        unknown = [item for item in value if item not in option_ids]
        if unknown:
            raise AnswerValidationError(question_id, f"多选答案包含未知选项：{unknown}")
        minimum = validation.get("min_selections")
        maximum = validation.get("max_selections")
        if minimum is not None and len(value) < minimum:
            raise AnswerValidationError(question_id, f"至少选择 {minimum} 项")
        if maximum is not None and len(value) > maximum:
            raise AnswerValidationError(question_id, f"最多选择 {maximum} 项")
        return AnswerResult(True, value)

    if question_type == "text":
        if not isinstance(value, str):
            raise AnswerValidationError(question_id, "文本题答案必须是字符串")
        minimum = validation.get("min_length")
        maximum = validation.get("max_length")
        if minimum is not None and len(value) < minimum:
            raise AnswerValidationError(question_id, f"文本长度不能少于 {minimum}")
        if maximum is not None and len(value) > maximum:
            raise AnswerValidationError(question_id, f"文本长度不能超过 {maximum}")
        return AnswerResult(True, value)

    if question_type == "number":
        if not _valid_number(value):
            raise AnswerValidationError(question_id, "数字题只接受有限 JSON 数字，不能使用布尔值或数字字符串")
        if validation.get("integer_only") and not float(value).is_integer():
            raise AnswerValidationError(question_id, "该题只接受整数")
        minimum = validation.get("min_value")
        maximum = validation.get("max_value")
        if minimum is not None and value < minimum:
            raise AnswerValidationError(question_id, f"数值不能小于 {minimum}")
        if maximum is not None and value > maximum:
            raise AnswerValidationError(question_id, f"数值不能大于 {maximum}")
        normalized = int(value) if validation.get("integer_only") else value
        return AnswerResult(True, normalized)

    raise AnswerValidationError(question_id, "未知题目类型")


def _issue(question_id: str | None, field: str, message: str) -> dict[str, Any]:
    return {"question_id": question_id, "field": field, "message": message}


def validate_survey_definition(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not questions:
        return [_issue(None, "questions", "发布前至少需要一道题")]

    ids = [question.get("id") for question in questions]
    if any(not isinstance(item, str) or not item for item in ids):
        issues.append(_issue(None, "questions.id", "每道题都必须具有稳定 ID"))
    duplicate_ids = {item for item in ids if ids.count(item) > 1}
    if duplicate_ids:
        issues.append(_issue(None, "questions.id", f"题目 ID 重复：{sorted(duplicate_ids)}"))
    position = {question_id: index for index, question_id in enumerate(ids)}

    for index, question in enumerate(questions):
        question_id = question.get("id") or f"index:{index}"
        question_type = question.get("type")
        title = question.get("title")
        options = question.get("options", [])
        validation = question.get("validation", {})
        rules = question.get("rules", [])

        if question_type not in {"single_choice", "multiple_choice", "text", "number"}:
            issues.append(_issue(question_id, "type", "题目类型不合法"))
            continue
        if not isinstance(title, str) or not title.strip():
            issues.append(_issue(question_id, "title", "题目标题不能为空"))

        option_ids: list[str] = []
        if question_type in {"single_choice", "multiple_choice"}:
            if not isinstance(options, list) or len(options) < 2:
                issues.append(_issue(question_id, "options", "单选和多选题至少需要两个选项"))
            else:
                option_ids = [option.get("id") for option in options]
                if any(not isinstance(item, str) or not item for item in option_ids):
                    issues.append(_issue(question_id, "options.id", "每个选项都必须具有稳定 ID"))
                if len(option_ids) != len(set(option_ids)):
                    issues.append(_issue(question_id, "options.id", "选项 ID 不能重复"))
                if any(not isinstance(option.get("label"), str) or not option["label"].strip() for option in options):
                    issues.append(_issue(question_id, "options.label", "选项标题不能为空"))
        elif options:
            issues.append(_issue(question_id, "options", "文本或数字题不能配置选项"))

        allowed_validation = {
            "single_choice": set(),
            "multiple_choice": {"min_selections", "max_selections"},
            "text": {"min_length", "max_length"},
            "number": {"min_value", "max_value", "integer_only"},
        }[question_type]
        unexpected = set(validation) - allowed_validation
        if unexpected:
            issues.append(_issue(question_id, "validation", f"当前题型不支持这些约束：{sorted(unexpected)}"))

        if question_type == "multiple_choice":
            minimum = validation.get("min_selections")
            maximum = validation.get("max_selections")
            for field, value in (("min_selections", minimum), ("max_selections", maximum)):
                if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
                    issues.append(_issue(question_id, field, "必须是非负整数"))
            if isinstance(minimum, int) and isinstance(maximum, int) and minimum > maximum:
                issues.append(_issue(question_id, "validation", "最少选择数不能大于最多选择数"))
            if isinstance(maximum, int) and maximum > len(option_ids):
                issues.append(_issue(question_id, "max_selections", "最多选择数不能超过选项数"))

        if question_type == "text":
            minimum = validation.get("min_length")
            maximum = validation.get("max_length")
            for field, value in (("min_length", minimum), ("max_length", maximum)):
                if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
                    issues.append(_issue(question_id, field, "必须是非负整数"))
            if isinstance(minimum, int) and isinstance(maximum, int) and minimum > maximum:
                issues.append(_issue(question_id, "validation", "最短长度不能大于最长长度"))

        if question_type == "number":
            minimum = validation.get("min_value")
            maximum = validation.get("max_value")
            for field, value in (("min_value", minimum), ("max_value", maximum)):
                if value is not None and not _valid_number(value):
                    issues.append(_issue(question_id, field, "必须是有限数字"))
            if _valid_number(minimum) and _valid_number(maximum) and minimum > maximum:
                issues.append(_issue(question_id, "validation", "最小值不能大于最大值"))
            integer_only = validation.get("integer_only")
            if integer_only is not None and not isinstance(integer_only, bool):
                issues.append(_issue(question_id, "integer_only", "必须是布尔值"))

        priorities = [rule.get("priority") for rule in rules]
        if len(priorities) != len(set(priorities)):
            issues.append(_issue(question_id, "rules.priority", "同一题的规则优先级不能重复"))
        expected_operators = {
            "single_choice": {"eq"},
            "multiple_choice": {"contains_any", "contains_all"},
            "number": {"eq", "gt", "gte", "lt", "lte"},
            "text": set(),
        }[question_type]
        for rule in rules:
            operator = rule.get("operator")
            value = rule.get("value")
            target = rule.get("target_question_id")
            if operator not in expected_operators:
                issues.append(_issue(question_id, "rules.operator", f"运算符 {operator!r} 不适用于当前题型"))
            if target not in position:
                issues.append(_issue(question_id, "rules.target_question_id", "跳转目标题不存在"))
            elif position[target] <= index:
                issues.append(_issue(question_id, "rules.target_question_id", "第一阶段只允许向后跳转"))
            if question_type == "single_choice" and value not in option_ids:
                issues.append(_issue(question_id, "rules.value", "单选规则值必须属于本题选项"))
            elif question_type == "multiple_choice":
                if not isinstance(value, list) or not value or any(item not in option_ids for item in value):
                    issues.append(_issue(question_id, "rules.value", "多选规则值必须是非空且属于本题的选项 ID 数组"))
            elif question_type == "number" and not _valid_number(value):
                issues.append(_issue(question_id, "rules.value", "数字规则值必须是有限数字"))
    return issues
