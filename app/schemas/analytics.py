from datetime import datetime

from pydantic import BaseModel, ConfigDict


class URLAnalyticsResponse(BaseModel):
    short_code: str
    original_url: str
    total_clicks: int
    created_at: datetime
    last_clicked_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
