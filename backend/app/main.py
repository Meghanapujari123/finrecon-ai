import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.batches import router as batches_router
from app.api.exceptions import router as exceptions_router
from app.api.misc import audit_router, dashboard_router, evaluation_router, forecast_router, health_router, qa_router
from app.api.reconciliation import router as reconciliation_router
from app.api.records import bank_router, ledger_router, payments_router
from app.config import get_settings
from app.database import init_db

settings = get_settings()

logging.basicConfig(level=settings.LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("finrecon")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("FinRecon AI backend started. LLM configured: %s", settings.llm_configured)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="AI Finance Controller for Reconciliation, Investigation & Revenue Intelligence",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(batches_router)
app.include_router(payments_router)
app.include_router(bank_router)
app.include_router(ledger_router)
app.include_router(reconciliation_router)
app.include_router(exceptions_router)
app.include_router(dashboard_router)
app.include_router(audit_router)
app.include_router(evaluation_router)
app.include_router(forecast_router)
app.include_router(qa_router)
