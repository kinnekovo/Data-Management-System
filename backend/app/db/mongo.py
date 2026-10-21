from collections.abc import Callable

from pymongo import MongoClient
from pymongo.database import Database

from app.db.schema import COLLECTION_VALIDATORS, INDEX_DEFINITIONS


def create_mongo_client(uri: str, timeout_ms: int) -> MongoClient:
    return MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)


def ensure_collection_schemas(database: Database) -> None:
    existing = set(database.list_collection_names())
    for collection_name, validator in COLLECTION_VALIDATORS.items():
        if collection_name not in existing:
            database.create_collection(
                collection_name,
                validator=validator,
                validationLevel="moderate",
                validationAction="error",
            )
            continue
        database.command(
            {
                "collMod": collection_name,
                "validator": validator,
                "validationLevel": "moderate",
                "validationAction": "error",
            }
        )


def ensure_indexes(database: Database) -> None:
    for collection_name, definitions in INDEX_DEFINITIONS.items():
        for keys, options in definitions:
            database[collection_name].create_index(keys, **options)


def ensure_database_schema(database: Database) -> None:
    ensure_collection_schemas(database)
    ensure_indexes(database)


MongoClientFactory = Callable[[str, int], MongoClient]
