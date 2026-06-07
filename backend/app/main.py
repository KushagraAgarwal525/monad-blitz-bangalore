from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import agent, analytics, marketplace, repositories, wallet


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Memoria API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(repositories.router)
app.include_router(marketplace.router)
app.include_router(agent.router)
app.include_router(analytics.router)
app.include_router(wallet.router)

if settings.enable_demo_flow:
    from app.demo.router import router as demo_router

    app.include_router(demo_router)


@app.get("/")
async def root():
    return {
        "name": "Memoria API",
        "version": "0.1.0",
        "tagline": "Cognition lives off-chain. Ownership lives on Monad.",
        "docs": "/docs",
        "health": "/health",
        "note": "This is the API server. Open the dashboard at http://localhost:3000",
        "endpoints": {
            "repositories": "/repositories",
            "marketplace": "/marketplace/repositories",
            "agent": "/agent/chat",
            "provenance": "/repositories/{id}/provenance/verify",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok", "tagline": "Cognition lives off-chain. Ownership lives on Monad."}


@app.get("/metadata/{repo_id}.json")
async def get_metadata_json(repo_id: str):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.database import async_session
    from app.models import MemoryRepository

    async with async_session() as db:
        repo = (
            await db.execute(
                select(MemoryRepository)
                .options(selectinload(MemoryRepository.display_metadata))
                .where(MemoryRepository.id == repo_id)
            )
        ).scalar_one_or_none()
        if not repo or not repo.display_metadata:
            return {"title": "Unknown", "description": ""}
        m = repo.display_metadata
        return {
            "title": m.title,
            "description": m.description,
            "display_tags": m.display_tags,
            "category": m.category,
            "image": m.image,
            "cover_photo": m.cover_photo,
            "version": m.version,
        }
