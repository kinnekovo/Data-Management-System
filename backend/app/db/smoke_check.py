import json
from uuid import uuid4

from app.core.config import get_settings
from app.db.mongo import create_mongo_client, ensure_database_schema
from app.db.schema import EXPECTED_INDEX_NAMES

SMOKE_COLLECTION = "_m1_smoke"


def run() -> dict[str, object]:
    settings = get_settings()
    database_name = settings.mongodb_test_database
    if not database_name.endswith("_test"):
        raise RuntimeError("Refusing write check: MONGODB_TEST_DATABASE must end with '_test'")

    client = create_mongo_client(settings.mongodb_uri, settings.mongodb_timeout_ms)
    token = uuid4().hex
    document = {"_smoke_token": token, "purpose": "m1-infrastructure-check"}
    inserted = False
    try:
        client.admin.command("ping")
        database = client[database_name]
        ensure_database_schema(database)

        actual_indexes = {
            collection: set(database[collection].index_information())
            for collection in EXPECTED_INDEX_NAMES
        }
        missing = {
            collection: sorted(expected - actual_indexes[collection])
            for collection, expected in EXPECTED_INDEX_NAMES.items()
            if expected - actual_indexes[collection]
        }
        if missing:
            raise RuntimeError(f"Missing indexes: {missing}")

        collection = database[SMOKE_COLLECTION]
        collection.insert_one(document)
        inserted = True
        found = collection.find_one({"_smoke_token": token})
        if found is None:
            raise RuntimeError("Temporary smoke document could not be read back")
        return {
            "status": "passed",
            "database": database_name,
            "indexes_verified": sum(len(names) for names in EXPECTED_INDEX_NAMES.values()),
            "temporary_document_read": True,
        }
    finally:
        try:
            if inserted:
                deleted_count = client[database_name][SMOKE_COLLECTION].delete_one(
                    {"_smoke_token": token}
                ).deleted_count
                if deleted_count != 1:
                    raise RuntimeError("Temporary smoke document cleanup did not delete one record")
        finally:
            client.close()


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
