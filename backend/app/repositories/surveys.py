from bson import ObjectId
from pymongo.database import Database

from app.core.errors import AppError


def parse_object_id(value: str, resource: str = "资源") -> ObjectId:
    if not ObjectId.is_valid(value):
        raise AppError(404, "NOT_FOUND", f"{resource}不存在")
    return ObjectId(value)


def get_owned_survey(database: Database, survey_id: str, owner_id: ObjectId) -> dict:
    document = database.surveys.find_one(
        {"_id": parse_object_id(survey_id, "问卷"), "owner_id": owner_id}
    )
    if document is None:
        raise AppError(404, "SURVEY_NOT_FOUND", "问卷不存在或无权访问")
    return document


def get_public_survey(database: Database, slug: str) -> dict:
    document = database.surveys.find_one({"slug": slug})
    if document is None:
        raise AppError(404, "SURVEY_NOT_FOUND", "问卷不存在")
    return document
