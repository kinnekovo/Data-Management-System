from pydantic import BaseModel, Field, field_validator


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_\-\u4e00-\u9fff]+$")
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip()


class UserView(BaseModel):
    id: str
    username: str
    created_at: str


class TokenView(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: str
    user: UserView
