from collections.abc import Callable

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database

USERS_COLLECTION = "users"
SURVEYS_COLLECTION = "surveys"
RESPONSES_COLLECTION = "responses"

EXPECTED_INDEX_NAMES = {
    USERS_COLLECTION: {"ux_users_username"},
    SURVEYS_COLLECTION: {"ux_surveys_slug", "ix_surveys_owner_created"},
    RESPONSES_COLLECTION: {
        "ix_responses_survey_submitted",
        "ux_responses_submission_guard",
    },
}


def create_mongo_client(uri: str, timeout_ms: int) -> MongoClient:
    return MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)


def ensure_indexes(database: Database) -> None:
    database[USERS_COLLECTION].create_index(
        [("username", ASCENDING)], unique=True, name="ux_users_username"
    )
    database[SURVEYS_COLLECTION].create_index(
        [("slug", ASCENDING)], unique=True, name="ux_surveys_slug"
    )
    database[SURVEYS_COLLECTION].create_index(
        [("owner_id", ASCENDING), ("created_at", DESCENDING)],
        name="ix_surveys_owner_created",
    )
    database[RESPONSES_COLLECTION].create_index(
        [("survey_id", ASCENDING), ("submitted_at", DESCENDING)],
        name="ix_responses_survey_submitted",
    )
    database[RESPONSES_COLLECTION].create_index(
        [("submission_guard", ASCENDING)],
        unique=True,
        partialFilterExpression={"submission_guard": {"$type": "string"}},
        name="ux_responses_submission_guard",
    )


MongoClientFactory = Callable[[str, int], MongoClient]
