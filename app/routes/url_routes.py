from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.rate_limiter import rate_limiter_dependency
from app.schemas.analytics import URLAnalyticsResponse
from app.schemas.url import URLCreateRequest, URLCreateResponse
from app.services.analytics_service import get_url_analytics, record_click
from app.services.url_service import create_short_url, get_original_url

SHORT_CODE_PATTERN = "^[a-zA-Z0-9]{6}$"

router = APIRouter(
    prefix="/api/v1", tags=["urls"], dependencies=[Depends(rate_limiter_dependency)]
)
redirect_router = APIRouter(
    tags=["redirects"], dependencies=[Depends(rate_limiter_dependency)]
)


@router.post(
    "/urls",
    response_model=URLCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create short URL",
    description="Shorten a long URL and receive a 6-character short code.",
)
async def create_url_endpoint(
    payload: URLCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    return await create_short_url(
        db=db,
        original_url=str(payload.url),
        base_url=settings.BASE_URL,
    )


@router.get(
    "/urls/{short_code}/analytics",
    response_model=URLAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get URL analytics",
    description="Retrieve click statistics for a short code.",
)
async def get_analytics_endpoint(
    short_code: str = Path(..., min_length=6, max_length=6, pattern=SHORT_CODE_PATTERN),
    db: AsyncSession = Depends(get_db),
):
    analytics = await get_url_analytics(db, short_code)
    if not analytics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Short URL not found",
        )
    return analytics


@redirect_router.get(
    "/{short_code}",
    response_class=RedirectResponse,
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    summary="Redirect short URL",
    description="Redirect short code to original target URL.",
)
async def redirect_endpoint(
    background_tasks: BackgroundTasks,
    short_code: str = Path(..., min_length=6, max_length=6, pattern=SHORT_CODE_PATTERN),
    db: AsyncSession = Depends(get_db),
):
    original_url = await get_original_url(db, short_code)
    if not original_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Short URL not found",
        )
    background_tasks.add_task(record_click, short_code)
    return RedirectResponse(
        url=original_url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
