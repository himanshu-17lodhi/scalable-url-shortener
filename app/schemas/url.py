from pydantic import BaseModel, HttpUrl


class URLCreateRequest(BaseModel):
    url: HttpUrl


class URLCreateResponse(BaseModel):
    short_code: str
    short_url: str
    original_url: str
