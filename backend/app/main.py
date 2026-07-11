from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.funds import router as funds_router
from app.models import Base, engine

Base.metadata.create_all(engine)

app = FastAPI(title="Mutual Fund Analyzer")
app.include_router(funds_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
