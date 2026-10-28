from bson import ObjectId
from pymongo.database import Database

from app.core.errors import AppError
from app.repositories.surveys import parse_object_id


def get_question(
    database: Database,
    question_id: str,
    user_id: ObjectId,
    *,
    require_owner: bool = False,
) -> dict:
    object_id = parse_object_id(question_id, "题目")
    question = database.questions.find_one({"_id": object_id})
    if question is None:
        raise AppError(404, "QUESTION_NOT_FOUND", "题目不存在或无权访问")
    if question["owner_id"] == user_id:
        return question
    if require_owner or database.question_shares.find_one(
        {"question_id": object_id, "grantee_user_id": user_id}
    ) is None:
        raise AppError(404, "QUESTION_NOT_FOUND", "题目不存在或无权访问")
    return question


def get_question_version(database: Database, question: dict, version_id: str) -> dict:
    version = database.question_versions.find_one(
        {
            "_id": parse_object_id(version_id, "题目版本"),
            "question_id": question["_id"],
        }
    )
    if version is None:
        raise AppError(404, "QUESTION_VERSION_NOT_FOUND", "题目版本不存在")
    return version


def get_owned_bank(database: Database, bank_id: str, owner_id: ObjectId) -> dict:
    bank = database.question_banks.find_one(
        {"_id": parse_object_id(bank_id, "题库"), "owner_id": owner_id}
    )
    if bank is None:
        raise AppError(404, "QUESTION_BANK_NOT_FOUND", "题库不存在或无权访问")
    return bank
