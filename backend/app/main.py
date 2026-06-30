from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import upload, invoices, dashboard, health, process

app = FastAPI(
    title="InvoiceAgent API",
    description="Système agentic de traitement de factures multilingues (FR/AR)",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router,   prefix="/health",    tags=["health"])
app.include_router(upload.router,   prefix="/upload",    tags=["upload"])
app.include_router(invoices.router, prefix="/invoices",  tags=["invoices"])
app.include_router(dashboard.router,prefix="/dashboard", tags=["dashboard"])
app.include_router(process.router,  prefix="/process",   tags=["process"])
