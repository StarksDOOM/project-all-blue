from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, func, select

from database import get_db_session, init_db
from models import PropertyListing


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