from pydantic import BaseModel, Field, HttpUrl


class URLCreateRequest(BaseModel):
    url: HttpUrl = Field(..., max_length=2048)


class URLCreateResponse(BaseModel):
    short_code: str
    short_url: str
    original_url: str
