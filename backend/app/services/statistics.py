from typing import Any

from pymongo.database import Database


def _answer_match(survey_id: Any, question_id: str) -> list[dict[str, Any]]:
    return [
        {"$match": {"survey_id": survey_id}},
        {"$unwind": "$answers"},
        {"$match": {"answers.question_id": question_id}},
    ]


def choice_statistics(database: Database, survey: dict, question: dict) -> dict[str, Any]:
    pipeline = _answer_match(survey["_id"], question["id"])
    if question["type"] == "multiple_choice":
        pipeline.append({"$unwind": "$answers.value"})
    pipeline.extend(
        [
            {"$group": {"_id": "$answers.value", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]
    )
    counts = {str(item["_id"]): item["count"] for item in database.responses.aggregate(pipeline)}
    answered_count = database.responses.count_documents(
        {"survey_id": survey["_id"], "answers.question_id": question["id"]}
    )
    return {
        "question_id": question["id"],
        "title": question["title"],
        "type": question["type"],
        "answered_count": answered_count,
        "options": [
            {"id": option["id"], "label": option["label"], "count": counts.get(option["id"], 0)}
            for option in question.get("options", [])
        ],
    }


def number_statistics(database: Database, survey: dict, question: dict) -> dict[str, Any]:
    pipeline = _answer_match(survey["_id"], question["id"])
    pipeline.append(
        {
            "$group": {
                "_id": None,
                "answered_count": {"$sum": 1},
                "average": {"$avg": "$answers.value"},
                "minimum": {"$min": "$answers.value"},
                "maximum": {"$max": "$answers.value"},
            }
        }
    )
    row = next(database.responses.aggregate(pipeline), None)
    return {
        "question_id": question["id"],
        "title": question["title"],
        "type": "number",
        "answered_count": row["answered_count"] if row else 0,
        "average": row["average"] if row else None,
        "minimum": row["minimum"] if row else None,
        "maximum": row["maximum"] if row else None,
    }


def text_summary(database: Database, survey: dict, question: dict) -> dict[str, Any]:
    return {
        "question_id": question["id"],
        "title": question["title"],
        "type": "text",
        "answered_count": database.responses.count_documents(
            {"survey_id": survey["_id"], "answers.question_id": question["id"]}
        ),
    }


def question_summary(database: Database, survey: dict, question: dict) -> dict[str, Any]:
    if question["type"] in {"single_choice", "multiple_choice"}:
        return choice_statistics(database, survey, question)
    if question["type"] == "number":
        return number_statistics(database, survey, question)
    return text_summary(database, survey, question)


def text_details(
    database: Database,
    survey: dict,
    question: dict,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    total = database.responses.count_documents(
        {"survey_id": survey["_id"], "answers.question_id": question["id"]}
    )
    pipeline = _answer_match(survey["_id"], question["id"])
    pipeline.extend(
        [
            {"$sort": {"submitted_at": -1}},
            {"$skip": (page - 1) * page_size},
            {"$limit": page_size},
            {"$project": {"_id": 0, "value": "$answers.value", "submitted_at": 1}},
        ]
    )
    items = [
        {"value": item["value"], "submitted_at": item["submitted_at"]}
        for item in database.responses.aggregate(pipeline)
    ]
    result = text_summary(database, survey, question)
    result.update({"page": page, "page_size": page_size, "total": total, "items": items})
    return result
