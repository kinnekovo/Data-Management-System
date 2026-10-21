from typing import Any

from pymongo import ASCENDING, DESCENDING

USERS_COLLECTION = "users"
SURVEYS_COLLECTION = "surveys"
RESPONSES_COLLECTION = "responses"

# MongoDB collection validators intentionally constrain the stable storage
# contract only. Question-type-specific rules are enforced by the service layer
# because they depend on multiple fields and on the order of other questions.
COLLECTION_VALIDATORS: dict[str, dict[str, Any]] = {
    USERS_COLLECTION: {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["username", "password_hash", "created_at"],
            "properties": {
                "username": {"bsonType": "string", "minLength": 3, "maxLength": 32},
                "password_hash": {"bsonType": "string"},
                "created_at": {"bsonType": "date"},
            },
        }
    },
    SURVEYS_COLLECTION: {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "owner_id",
                "slug",
                "title",
                "status",
                "questions",
                "schema_version",
                "definition_version",
                "created_at",
                "updated_at",
            ],
            "properties": {
                "owner_id": {"bsonType": "objectId"},
                "slug": {"bsonType": "string"},
                "title": {"bsonType": "string", "minLength": 1, "maxLength": 200},
                "description": {"bsonType": "string", "maxLength": 5000},
                "allow_anonymous": {"bsonType": "bool"},
                "allow_multiple_submissions": {"bsonType": "bool"},
                "status": {"enum": ["draft", "published", "closed"]},
                "expires_at": {"bsonType": ["date", "null"]},
                "questions": {"bsonType": "array"},
                "schema_version": {"bsonType": "int", "minimum": 1},
                "definition_version": {"bsonType": "int", "minimum": 1},
                "created_at": {"bsonType": "date"},
                "updated_at": {"bsonType": "date"},
                "published_at": {"bsonType": ["date", "null"]},
                "closed_at": {"bsonType": ["date", "null"]},
            },
        }
    },
    RESPONSES_COLLECTION: {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "survey_id",
                "respondent_id",
                "definition_version",
                "answers",
                "submitted_at",
            ],
            "properties": {
                "survey_id": {"bsonType": "objectId"},
                "respondent_id": {"bsonType": "objectId"},
                "definition_version": {"bsonType": "int", "minimum": 1},
                "answers": {"bsonType": "array"},
                "submission_guard": {"bsonType": ["string", "null"]},
                "submitted_at": {"bsonType": "date"},
            },
        }
    },
}

INDEX_DEFINITIONS: dict[str, list[tuple[list[tuple[str, int]], dict[str, Any]]]] = {
    USERS_COLLECTION: [
        ([("username", ASCENDING)], {"unique": True, "name": "ux_users_username"}),
    ],
    SURVEYS_COLLECTION: [
        ([("slug", ASCENDING)], {"unique": True, "name": "ux_surveys_slug"}),
        (
            [("owner_id", ASCENDING), ("created_at", DESCENDING)],
            {"name": "ix_surveys_owner_created"},
        ),
    ],
    RESPONSES_COLLECTION: [
        (
            [("survey_id", ASCENDING), ("submitted_at", DESCENDING)],
            {"name": "ix_responses_survey_submitted"},
        ),
        (
            [("submission_guard", ASCENDING)],
            {
                "unique": True,
                "partialFilterExpression": {"submission_guard": {"$type": "string"}},
                "name": "ux_responses_submission_guard",
            },
        ),
    ],
}

EXPECTED_INDEX_NAMES = {
    collection: {options["name"] for _, options in definitions}
    for collection, definitions in INDEX_DEFINITIONS.items()
}
