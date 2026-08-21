import logging
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.click import Click
from app.models.url import URL
from app.schemas.analytics import URLAnalyticsResponse

logger = logging.getLogger(__name__)


async def record_click(short_code: str) -> None:
    """
    Background task to record a click event in PostgreSQL out-of-band.
    Operates using its own AsyncSessionLocal database session.
    """
    async with AsyncSessionLocal() as session:
        try:
            stmt = select(URL.id).where(URL.short_code == short_code)
            result = await session.execute(stmt)
            url_id = result.scalar_one_or_none()
            if url_id is not None:
                click_obj = Click(url_id=url_id)
                session.add(click_obj)
                await session.commit()
            else:
                logger.warning(
                    f"Could not record click: short_code '{short_code}' not found."
                )
        except Exception as exc:
            logger.error(f"Failed to record click for '{short_code}': {exc}")


async def get_url_analytics(
    db: AsyncSession, short_code: str
) -> URLAnalyticsResponse | None:
    """
    Retrieve click statistics (total clicks, created_at, last_clicked_at) for a short code.
    """
    stmt = select(URL).where(URL.short_code == short_code)
    result = await db.execute(stmt)
    url_obj = result.scalar_one_or_none()
    if not url_obj:
        return None

    click_stmt = select(
        func.count(Click.id).label("total_clicks"),
        func.max(Click.clicked_at).label("last_clicked_at"),
    ).where(Click.url_id == url_obj.id)
    click_result = await db.execute(click_stmt)
    row = click_result.one()

    return URLAnalyticsResponse(
        short_code=url_obj.short_code,
        original_url=url_obj.original_url,
        total_clicks=row.total_clicks or 0,
        created_at=url_obj.created_at,
        last_clicked_at=row.last_clicked_at,
    )
