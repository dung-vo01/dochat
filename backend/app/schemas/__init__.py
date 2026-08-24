from datetime import datetime

from pydantic import BaseModel


class ConversationCreate(BaseModel):
    title: str = "New chat"


class ConversationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: str
    created_at: datetime


class MessageResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    role: str
    content: str
    created_at: datetime


class ChatRequest(BaseModel):
    conversation_id: int
    message: str


class ConversationDetail(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: str
    created_at: datetime
    messages: list[MessageResponse]
