"""Idempotently migrate embedded stage-one questions to phase-two library records.

Preview by default. Pass --apply to write changes.
"""

import argparse
import json
from typing import Any

from bson import ObjectId

from app.core.config import get_settings
from app.db.mongo import create_mongo_client, ensure_database_schema
from app.schemas.common import utc_now


def _version_from_embedded(
    question: dict[str, Any],
    owner_id: ObjectId,
    migration_key: str,
    *,
    question_id: ObjectId | None = None,
    version_id: ObjectId | None = None,
) -> tuple[dict, dict]:
    now = utc_now()
    question_id = question_id or ObjectId()
    version_id = version_id or ObjectId()
    version = {
        "_id": version_id,
        "question_id": question_id,
        "version_no": 1,
        "parent_version_id": None,
        "created_by": owner_id,
        "title": question["title"],
        "type": question["type"],
        "options": question.get("options", []),
        "validation": question.get("validation", {}),
        "change_note": "从第一阶段问卷迁移",
        "created_at": now,
    }
    library_question = {
        "_id": question_id,
        "owner_id": owner_id,
        "current_version_id": version_id,
        "archived": False,
        "migration_key": migration_key,
        "created_at": now,
        "updated_at": now,
    }
    return library_question, version


def migrate(database, *, apply: bool) -> dict[str, Any]:
    report = {
        "mode": "apply" if apply else "preview",
        "surveys_scanned": 0,
        "surveys_changed": 0,
        "questions_created": 0,
        "responses_changed": 0,
    }
    for survey in database.surveys.find({}):
        report["surveys_scanned"] += 1
        questions = list(survey.get("questions", []))
        mapping: dict[str, tuple[ObjectId, ObjectId]] = {}
        changed = False
        for embedded in questions:
            if embedded.get("question_id") and embedded.get("question_version_id"):
                mapping[embedded["id"]] = (
                    embedded["question_id"],
                    embedded["question_version_id"],
                )
                continue
            migration_key = f"{survey['_id']}:{embedded['id']}"
            existing = database.questions.find_one({"migration_key": migration_key})
            if existing:
                library_question = existing
                version = database.question_versions.find_one(
                    {"_id": existing["current_version_id"]}
                )
                if version is None:
                    library_question, version = _version_from_embedded(
                        embedded,
                        survey["owner_id"],
                        migration_key,
                        question_id=existing["_id"],
                        version_id=existing["current_version_id"],
                    )
            else:
                library_question, version = _version_from_embedded(
                    embedded, survey["owner_id"], migration_key
                )
            embedded["question_id"] = library_question["_id"]
            embedded["question_version_id"] = version["_id"]
            embedded["version_no"] = version["version_no"]
            mapping[embedded["id"]] = (library_question["_id"], version["_id"])
            changed = True
            report["questions_created"] += 1
            if apply:
                if existing is None:
                    database.questions.insert_one(library_question)
                if database.question_versions.find_one({"_id": version["_id"]}) is None:
                    database.question_versions.insert_one(version)
        if changed:
            report["surveys_changed"] += 1
            if apply:
                database.surveys.update_one(
                    {"_id": survey["_id"]},
                    {"$set": {"questions": questions, "schema_version": 2}},
                )

        for response in database.responses.find({"survey_id": survey["_id"]}):
            answers = list(response.get("answers", []))
            answer_changed = False
            for answer in answers:
                source = mapping.get(answer.get("question_id"))
                if source and not answer.get("library_question_id"):
                    answer["library_question_id"], answer["question_version_id"] = source
                    answer_changed = True
            if answer_changed:
                report["responses_changed"] += 1
                if apply:
                    database.responses.update_one(
                        {"_id": response["_id"]}, {"$set": {"answers": answers}}
                    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate questionnaire data to phase two")
    parser.add_argument("--database", help="Override the configured MongoDB database")
    parser.add_argument("--apply", action="store_true", help="Write the migration")
    arguments = parser.parse_args()
    settings = get_settings()
    database_name = arguments.database or settings.mongodb_database
    client = create_mongo_client(settings.mongodb_uri, settings.mongodb_timeout_ms)
    try:
        client.admin.command("ping")
        database = client[database_name]
        ensure_database_schema(database)
        print(json.dumps(migrate(database, apply=arguments.apply), ensure_ascii=False))
    finally:
        client.close()


if __name__ == "__main__":
    main()
