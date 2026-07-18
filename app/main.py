import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.infrastructure.database import init_db
from app.presentation.v1.authorization.discord_controller import router as discord_router
from app.presentation.v1.authorization.google_controller import router as google_router
from app.presentation.v1.authorization.user_controller import router as user_router
from app.presentation.v1.bets.bets_controller import router as bets_router
from app.presentation.v1.categories.categories_controller import router as categories_router
from app.presentation.v1.diaries.diaries_controller import router as diaries_router
from app.presentation.v1.group.group_controller import router as group_router
from app.presentation.v1.todos.todos_controller import router as todos_router


Path("uploads").mkdir(exist_ok=True)

DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://tlitodos.vercel.app",
]


def cors_origins() -> list[str]:
    extra_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()]
    return DEFAULT_CORS_ORIGINS + extra_origins


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="TLITODOS Backend", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
    app.include_router(google_router)
    app.include_router(user_router)
    app.include_router(discord_router)
    app.include_router(group_router)
    app.include_router(categories_router)
    app.include_router(todos_router)
    app.include_router(bets_router)
    app.include_router(diaries_router)

    return app


app = create_app()


@app.get("/ping", tags=["You good? right?"])
async def ping():
    return "pong"
