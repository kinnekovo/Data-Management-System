from app.db.mongo import ensure_indexes
from app.db.schema import EXPECTED_INDEX_NAMES


class RecordingCollection:
    def __init__(self):
        self.calls = []

    def create_index(self, keys, **kwargs):
        self.calls.append((keys, kwargs))
        return kwargs["name"]


class RecordingDatabase:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        return self.collections.setdefault(name, RecordingCollection())


def test_ensure_indexes_creates_stable_expected_definitions():
    database = RecordingDatabase()
    ensure_indexes(database)

    actual_names = {
        collection: {kwargs["name"] for _, kwargs in recorder.calls}
        for collection, recorder in database.collections.items()
    }
    assert actual_names == EXPECTED_INDEX_NAMES

    response_calls = database.collections["responses"].calls
    guard = next(kwargs for _, kwargs in response_calls if kwargs["name"] == "ux_responses_submission_guard")
    assert guard["unique"] is True
    assert guard["partialFilterExpression"] == {
        "submission_guard": {"$type": "string"}
    }
