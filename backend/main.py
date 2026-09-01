from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers.chat import router as chat_router
from app.routers.conversations import router as conversations_router
from app.routers.documents import router as documents_router

app = FastAPI(title="Dochat API", version="1.0.0")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.ALLOW_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(conversations_router)
app.include_router(documents_router)
