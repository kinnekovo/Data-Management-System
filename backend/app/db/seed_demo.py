import argparse
import json
from secrets import token_urlsafe

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.mongo import create_mongo_client, ensure_indexes
from app.schemas.common import utc_now
from app.services.rule_engine import replay_path

DEMO_MARKER = "stage1_demo_v1"
DEMO_PASSWORD = "DemoPass123!"


def question_definition() -> list[dict]:
    return [
        {
            "id": "q_experience",
            "type": "single_choice",
            "title": "你是否使用过 MongoDB？",
            "required": True,
            "options": [
                {"id": "opt_yes", "label": "使用过"},
                {"id": "opt_no", "label": "尚未使用"},
            ],
            "validation": {},
            "rules": [
                {
                    "priority": 1,
                    "operator": "eq",
                    "value": "opt_yes",
                    "target_question_id": "q_features",
                }
            ],
        },
        {
            "id": "q_expectation",
            "type": "text",
            "title": "你希望先了解什么？",
            "required": True,
            "options": [],
            "validation": {"min_length": 2, "max_length": 100},
            "rules": [],
        },
        {
            "id": "q_features",
            "type": "multiple_choice",
            "title": "你关注哪些 MongoDB 特性？",
            "required": True,
            "options": [
                {"id": "opt_document", "label": "文档模型"},
                {"id": "opt_aggregate", "label": "聚合管道"},
                {"id": "opt_index", "label": "索引"},
            ],
            "validation": {"min_selections": 1, "max_selections": 2},
            "rules": [],
        },
        {
            "id": "q_score",
            "type": "number",
            "title": "请为课程体验打分",
            "required": True,
            "options": [],
            "validation": {"min_value": 0, "max_value": 100, "integer_only": True},
            "rules": [],
        },
    ]


def run(database_name: str) -> dict:
    if not database_name.endswith("_demo"):
        raise RuntimeError("Refusing demo seed: database name must end with '_demo'")
    settings = get_settings()
    client = create_mongo_client(settings.mongodb_uri, settings.mongodb_timeout_ms)
    try:
        client.admin.command("ping")
        database = client[database_name]
        ensure_indexes(database)

        previous_surveys = list(database.surveys.find({"demo_marker": DEMO_MARKER}, {"_id": 1}))
        previous_survey_ids = [item["_id"] for item in previous_surveys]
        if previous_survey_ids:
            database.responses.delete_many({"survey_id": {"$in": previous_survey_ids}, "demo_marker": DEMO_MARKER})
        database.surveys.delete_many({"demo_marker": DEMO_MARKER})
        database.users.delete_many({"demo_marker": DEMO_MARKER})

        now = utc_now()
        users = []
        for username in ("demo_creator", "demo_respondent"):
            document = {
                "username": username,
                "password_hash": hash_password(DEMO_PASSWORD),
                "created_at": now,
                "demo_marker": DEMO_MARKER,
            }
            document["_id"] = database.users.insert_one(document).inserted_id
            users.append(document)

        survey = {
            "owner_id": users[0]["_id"],
            "slug": f"demo{token_urlsafe(8).replace('-', '').replace('_', '')}",
            "title": "MongoDB 课程体验演示问卷",
            "description": "包含四种底层题型、单选跳转和实时统计的演示数据。",
            "allow_anonymous": False,
            "allow_multiple_submissions": False,
            "status": "published",
            "expires_at": None,
            "questions": question_definition(),
            "schema_version": 1,
            "definition_version": 1,
            "created_at": now,
            "updated_at": now,
            "published_at": now,
            "closed_at": None,
            "demo_marker": DEMO_MARKER,
        }
        survey["_id"] = database.surveys.insert_one(survey).inserted_id

        submitted_answers = [
            {"question_id": "q_experience", "value": "opt_yes"},
            {"question_id": "q_features", "value": ["opt_document", "opt_aggregate"]},
            {"question_id": "q_score", "value": 88},
        ]
        normalized, _visited = replay_path(survey["questions"], submitted_answers)
        database.responses.insert_one(
            {
                "survey_id": survey["_id"],
                "respondent_id": users[1]["_id"],
                "definition_version": 1,
                "answers": normalized,
                "submission_guard": f"{survey['_id']}:{users[1]['_id']}",
                "submitted_at": now,
                "demo_marker": DEMO_MARKER,
            }
        )
        return {
            "status": "seeded",
            "database": database_name,
            "creator": "demo_creator",
            "respondent": "demo_respondent",
            "password": DEMO_PASSWORD,
            "survey_id": str(survey["_id"]),
            "slug": survey["slug"],
            "responses": 1,
        }
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed an isolated stage-one demo database")
    parser.add_argument("--database", required=True, help="Dedicated database name ending in _demo")
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.database), ensure_ascii=False))
