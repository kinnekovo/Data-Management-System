from fastapi import APIRouter, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.api.dependencies import CurrentUser, DatabaseDep
from app.api.questions import question_view, version_view
from app.core.errors import AppError
from app.repositories.questions import get_owned_bank, get_question, get_question_version
from app.schemas.common import iso_datetime, utc_now
from app.schemas.question import (
    QuestionBankCreate,
    QuestionBankItemCreate,
    QuestionBankItemUpdate,
    QuestionBankUpdate,
)

router = APIRouter(prefix="/question-banks", tags=["question-banks"])


def bank_view(database, bank: dict, *, include_items: bool = False) -> dict:
    result = {
        "id": str(bank["_id"]),
        "name": bank["name"],
        "description": bank.get("description", ""),
        "item_count": database.question_bank_items.count_documents({"bank_id": bank["_id"]}),
        "created_at": iso_datetime(bank["created_at"]),
        "updated_at": iso_datetime(bank["updated_at"]),
    }
    if include_items:
        items = []
        for entry in database.question_bank_items.find({"bank_id": bank["_id"]}).sort(
            "added_at", -1
        ):
            try:
                question = get_question(
                    database, str(entry["question_id"]), bank["owner_id"]
                )
            except AppError:
                continue
            version = database.question_versions.find_one({"_id": entry["default_version_id"]})
            if version is None:
                continue
            items.append(
                {
                    "question": question_view(database, question, user_id=bank["owner_id"]),
                    "default_version": version_view(version),
                    "added_at": iso_datetime(entry["added_at"]),
                }
            )
        result["items"] = items
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
def create_bank(
    payload: QuestionBankCreate, database: DatabaseDep, current_user: CurrentUser
) -> dict:
    now = utc_now()
    document = {
        "owner_id": current_user["_id"],
        "name": payload.name,
        "description": payload.description,
        "created_at": now,
        "updated_at": now,
    }
    document["_id"] = database.question_banks.insert_one(document).inserted_id
    return bank_view(database, document)


@router.get("")
def list_banks(database: DatabaseDep, current_user: CurrentUser) -> dict:
    return {
        "items": [
            bank_view(database, item)
            for item in database.question_banks.find({"owner_id": current_user["_id"]}).sort(
                "created_at", -1
            )
        ]
    }


@router.get("/{bank_id}")
def bank_detail(bank_id: str, database: DatabaseDep, current_user: CurrentUser) -> dict:
    bank = get_owned_bank(database, bank_id, current_user["_id"])
    return bank_view(database, bank, include_items=True)


@router.patch("/{bank_id}")
def update_bank(
    bank_id: str,
    payload: QuestionBankUpdate,
    database: DatabaseDep,
    current_user: CurrentUser,
) -> dict:
    bank = get_owned_bank(database, bank_id, current_user["_id"])
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return bank_view(database, bank, include_items=True)
    changes["updated_at"] = utc_now()
    updated = database.question_banks.find_one_and_update(
        {"_id": bank["_id"]}, {"$set": changes}, return_document=ReturnDocument.AFTER
    )
    return bank_view(database, updated, include_items=True)


@router.delete("/{bank_id}", status_code=204)
def delete_bank(bank_id: str, database: DatabaseDep, current_user: CurrentUser) -> None:
    bank = get_owned_bank(database, bank_id, current_user["_id"])
    database.question_bank_items.delete_many({"bank_id": bank["_id"]})
    database.question_banks.delete_one({"_id": bank["_id"]})


@router.post("/{bank_id}/items", status_code=status.HTTP_201_CREATED)
def add_bank_item(
    bank_id: str,
    payload: QuestionBankItemCreate,
    database: DatabaseDep,
    current_user: CurrentUser,
) -> dict:
    bank = get_owned_bank(database, bank_id, current_user["_id"])
    question = get_question(database, payload.question_id, current_user["_id"])
    version = (
        get_question_version(database, question, payload.default_version_id)
        if payload.default_version_id
        else database.question_versions.find_one({"_id": question["current_version_id"]})
    )
    document = {
        "bank_id": bank["_id"],
        "question_id": question["_id"],
        "default_version_id": version["_id"],
        "added_at": utc_now(),
    }
    try:
        database.question_bank_items.insert_one(document)
    except DuplicateKeyError:
        raise AppError(409, "QUESTION_ALREADY_IN_BANK", "题目已经在该题库中") from None
    database.question_banks.update_one(
        {"_id": bank["_id"]}, {"$set": {"updated_at": utc_now()}}
    )
    return {
        "question": question_view(database, question, user_id=current_user["_id"]),
        "default_version": version_view(version),
        "added_at": iso_datetime(document["added_at"]),
    }


@router.patch("/{bank_id}/items/{question_id}")
def update_bank_item(
    bank_id: str,
    question_id: str,
    payload: QuestionBankItemUpdate,
    database: DatabaseDep,
    current_user: CurrentUser,
) -> dict:
    bank = get_owned_bank(database, bank_id, current_user["_id"])
    question = get_question(database, question_id, current_user["_id"])
    version = get_question_version(database, question, payload.default_version_id)
    updated = database.question_bank_items.find_one_and_update(
        {"bank_id": bank["_id"], "question_id": question["_id"]},
        {"$set": {"default_version_id": version["_id"]}},
        return_document=ReturnDocument.AFTER,
    )
    if updated is None:
        raise AppError(404, "QUESTION_BANK_ITEM_NOT_FOUND", "题目不在该题库中")
    database.question_banks.update_one(
        {"_id": bank["_id"]}, {"$set": {"updated_at": utc_now()}}
    )
    return {
        "question": question_view(database, question, user_id=current_user["_id"]),
        "default_version": version_view(version),
        "added_at": iso_datetime(updated["added_at"]),
    }


@router.delete("/{bank_id}/items/{question_id}", status_code=204)
def delete_bank_item(
    bank_id: str,
    question_id: str,
    database: DatabaseDep,
    current_user: CurrentUser,
) -> None:
    bank = get_owned_bank(database, bank_id, current_user["_id"])
    question = get_question(database, question_id, current_user["_id"])
    database.question_bank_items.delete_one(
        {"bank_id": bank["_id"], "question_id": question["_id"]}
    )
    database.question_banks.update_one(
        {"_id": bank["_id"]}, {"$set": {"updated_at": utc_now()}}
    )
