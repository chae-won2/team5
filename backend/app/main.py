import logging
from pathlib import Path

from fastapi.staticfiles import StaticFiles

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import admin, geocode, merchants, notify, recommend, spots

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

app = FastAPI(title="Busan Full-Course API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(spots.router)
app.include_router(merchants.router)
app.include_router(recommend.router)
app.include_router(geocode.router)
app.include_router(notify.router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    return {"ok": True}


# Only the built frontend is public; source data and environment files stay private.
frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
