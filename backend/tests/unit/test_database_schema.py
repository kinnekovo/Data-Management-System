from app.db.mongo import ensure_collection_schemas
from app.db.schema import COLLECTION_VALIDATORS


class RecordingDatabase:
    def __init__(self, existing=()):
        self.existing = set(existing)
        self.created = []
        self.commands = []

    def list_collection_names(self):
        return list(self.existing)

    def create_collection(self, name, **options):
        self.created.append((name, options))

    def command(self, command):
        self.commands.append(command)


def test_collection_schemas_create_missing_collections():
    database = RecordingDatabase()
    ensure_collection_schemas(database)

    assert {name for name, _ in database.created} == set(COLLECTION_VALIDATORS)
    assert all(options["validationAction"] == "error" for _, options in database.created)
    assert database.commands == []


def test_collection_schemas_update_existing_collections():
    database = RecordingDatabase(existing=COLLECTION_VALIDATORS)
    ensure_collection_schemas(database)

    assert database.created == []
    assert {command["collMod"] for command in database.commands} == set(COLLECTION_VALIDATORS)
    assert all(command["validationLevel"] == "moderate" for command in database.commands)
