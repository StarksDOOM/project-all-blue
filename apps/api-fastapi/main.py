from contextlib import asynccontextmanager
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, func, select

from database import get_db_session, init_db
from models import PropertyListing
from services.sync_service import execute_portal_sync_background

SUPPORTED_CRAWL_PORTALS = {"remaxrd", "realtor"}
IMPLEMENTED_CRAWL_PORTALS = {"remaxrd"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="All Blue Core API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/properties", response_model=dict)
async def list_properties(
    session: Session = Depends(get_db_session),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    source_portal: Optional[str] = Query(default=None),
    sector: Optional[str] = Query(default=None),
):
    offset = (page - 1) * limit
    query = select(PropertyListing).where(PropertyListing.deleted_at == None)

    if source_portal:
        query = query.where(PropertyListing.source_portal == source_portal)
    if sector:
        query = query.where(PropertyListing.sector == sector)

    count_query = select(func.count()).select_from(query.subquery())
    total_count = session.exec(count_query).one()

    results = session.exec(query.offset(offset).limit(limit)).all()

    return {
        "metadata": {
            "total": total_count,
            "page": page,
            "limit": limit,
            "pages": (total_count + limit - 1) // limit,
        },
        "data": results,
    }


@app.post("/api/v1/properties/trigger-crawl", status_code=status.HTTP_202_ACCEPTED)
async def trigger_crawl(
    background_tasks: BackgroundTasks,
    source_portal: str = Query(
        ...,
        description="Portal driver key (e.g. remaxrd)",
    ),
):
    if source_portal not in SUPPORTED_CRAWL_PORTALS:
        raise HTTPException(
            status_code=400,
            detail=f"Scraper driver context '{source_portal}' is currently unsupported.",
        )

    if source_portal not in IMPLEMENTED_CRAWL_PORTALS:
        raise HTTPException(
            status_code=501,
            detail=f"Driver '{source_portal}' is registered but not yet implemented.",
        )

    background_tasks.add_task(execute_portal_sync_background, source_portal)

    return {
        "status": "queued",
        "driver": source_portal,
        "message": "Sync pipeline scheduled in background.",
    }