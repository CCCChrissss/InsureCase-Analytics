from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import CORS_ORIGINS
from backend.app.routers import cases, health, search, similar_cases, statistics, summaries


app = FastAPI(
    title="保險評議分析系統 API",
    description="FOI ODS 人壽保險評議資料查詢、搜尋與統計 API。",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(cases.router)
app.include_router(search.router)
app.include_router(similar_cases.router)
app.include_router(statistics.router)
app.include_router(summaries.router)
