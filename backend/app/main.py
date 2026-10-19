import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import PyMongoError

from app.api.health import router as health_router
from app.core.config import Settings, get_settings
from app.db.mongo import MongoClientFactory, create_mongo_client, ensure_indexes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    mongo_client_factory: MongoClientFactory = create_mongo_client,
) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        client = mongo_client_factory(app_settings.mongodb_uri, app_settings.mongodb_timeout_ms)
        app.state.mongodb_client = client
        app.state.mongodb_database = client[app_settings.mongodb_database]
        try:
            ensure_indexes(app.state.mongodb_database)
            logger.info("MongoDB indexes are ready")
        except PyMongoError:
            logger.warning("MongoDB unavailable during startup; readiness will report 503")
        yield
        client.close()

    app = FastAPI(
        title=app_settings.app_name,
        version="0.1.0",
        description="M1 infrastructure API",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type"],
    )
    app.include_router(health_router, prefix=app_settings.api_prefix)
    return app


app = create_app()
