from typing import Any

from pymongo import ASCENDING, DESCENDING

USERS_COLLECTION = "users"
SURVEYS_COLLECTION = "surveys"
RESPONSES_COLLECTION = "responses"
QUESTIONS_COLLECTION = "questions"
QUESTION_VERSIONS_COLLECTION = "question_versions"
QUESTION_SHARES_COLLECTION = "question_shares"
QUESTION_BANKS_COLLECTION = "question_banks"
QUESTION_BANK_ITEMS_COLLECTION = "question_bank_items"

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
    QUESTIONS_COLLECTION: {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["owner_id", "current_version_id", "archived", "created_at", "updated_at"],
            "properties": {
                "owner_id": {"bsonType": "objectId"},
                "current_version_id": {"bsonType": "objectId"},
                "archived": {"bsonType": "bool"},
                "migration_key": {"bsonType": "string"},
                "created_at": {"bsonType": "date"},
                "updated_at": {"bsonType": "date"},
            },
        }
    },
    QUESTION_VERSIONS_COLLECTION: {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "question_id", "version_no", "created_by", "title", "type",
                "options", "validation", "created_at",
            ],
            "properties": {
                "question_id": {"bsonType": "objectId"},
                "version_no": {"bsonType": "int", "minimum": 1},
                "parent_version_id": {"bsonType": ["objectId", "null"]},
                "created_by": {"bsonType": "objectId"},
                "title": {"bsonType": "string", "minLength": 1, "maxLength": 500},
                "type": {"enum": ["single_choice", "multiple_choice", "text", "number"]},
                "options": {"bsonType": "array"},
                "validation": {"bsonType": "object"},
                "change_note": {"bsonType": "string", "maxLength": 500},
                "created_at": {"bsonType": "date"},
            },
        }
    },
    QUESTION_SHARES_COLLECTION: {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["question_id", "grantee_user_id", "shared_by", "permission", "created_at"],
            "properties": {
                "question_id": {"bsonType": "objectId"},
                "grantee_user_id": {"bsonType": "objectId"},
                "shared_by": {"bsonType": "objectId"},
                "permission": {"enum": ["use"]},
                "created_at": {"bsonType": "date"},
            },
        }
    },
    QUESTION_BANKS_COLLECTION: {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["owner_id", "name", "description", "created_at", "updated_at"],
            "properties": {
                "owner_id": {"bsonType": "objectId"},
                "name": {"bsonType": "string", "minLength": 1, "maxLength": 100},
                "description": {"bsonType": "string", "maxLength": 1000},
                "created_at": {"bsonType": "date"},
                "updated_at": {"bsonType": "date"},
            },
        }
    },
    QUESTION_BANK_ITEMS_COLLECTION: {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["bank_id", "question_id", "default_version_id", "added_at"],
            "properties": {
                "bank_id": {"bsonType": "objectId"},
                "question_id": {"bsonType": "objectId"},
                "default_version_id": {"bsonType": "objectId"},
                "added_at": {"bsonType": "date"},
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
        (
            [("questions.question_id", ASCENDING), ("status", ASCENDING)],
            {"name": "ix_surveys_question_status"},
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
        (
            [("answers.library_question_id", ASCENDING), ("submitted_at", DESCENDING)],
            {"name": "ix_responses_library_question_submitted"},
        ),
        (
            [("answers.question_version_id", ASCENDING), ("submitted_at", DESCENDING)],
            {"name": "ix_responses_question_version_submitted"},
        ),
    ],
    QUESTIONS_COLLECTION: [
        (
            [("owner_id", ASCENDING), ("updated_at", DESCENDING)],
            {"name": "ix_questions_owner_updated"},
        ),
        (
            [("migration_key", ASCENDING)],
            {
                "unique": True,
                "partialFilterExpression": {"migration_key": {"$type": "string"}},
                "name": "ux_questions_migration_key",
            },
        ),
    ],
    QUESTION_VERSIONS_COLLECTION: [
        (
            [("question_id", ASCENDING), ("version_no", ASCENDING)],
            {"unique": True, "name": "ux_question_versions_number"},
        ),
        (
            [("question_id", ASCENDING), ("created_at", DESCENDING)],
            {"name": "ix_question_versions_created"},
        ),
    ],
    QUESTION_SHARES_COLLECTION: [
        (
            [("question_id", ASCENDING), ("grantee_user_id", ASCENDING)],
            {"unique": True, "name": "ux_question_shares_grantee"},
        ),
        (
            [("grantee_user_id", ASCENDING), ("created_at", DESCENDING)],
            {"name": "ix_question_shares_grantee_created"},
        ),
    ],
    QUESTION_BANKS_COLLECTION: [
        (
            [("owner_id", ASCENDING), ("created_at", DESCENDING)],
            {"name": "ix_question_banks_owner_created"},
        ),
    ],
    QUESTION_BANK_ITEMS_COLLECTION: [
        (
            [("bank_id", ASCENDING), ("question_id", ASCENDING)],
            {"unique": True, "name": "ux_question_bank_items_question"},
        ),
        (
            [("question_id", ASCENDING)],
            {"name": "ix_question_bank_items_question"},
        ),
    ],
}

EXPECTED_INDEX_NAMES = {
    collection: {options["name"] for _, options in definitions}
    for collection, definitions in INDEX_DEFINITIONS.items()
}
