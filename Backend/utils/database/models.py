from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


# User models
class UserRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="User's full name")
    email: EmailStr = Field(..., description="User's email address")
    phone_number: str = Field(..., min_length=10, max_length=15, description="User's phone number")


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    phone_number: str
    message: str


# Chat history models
class MessageCreate(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$", description="Message role")
    content: str = Field(..., min_length=1, description="Message content")


class ChatHistoryCreate(BaseModel):
    user_id: int = Field(..., description="User ID")
    title: Optional[str] = Field(None, description="Conversation title")


class MessageResponse(BaseModel):
    id: int
    chat_history_id: int
    role: str
    content: str
    created_at: str


class ChatHistoryResponse(BaseModel):
    id: int
    user_id: int
    title: str
    created_at: str
    message_count: Optional[int] = None


class ChatHistoryDetailResponse(BaseModel):
    id: int
    user_id: int
    title: str
    created_at: str
    messages: List[MessageResponse]


# Test credentials models
class TestCredentialsRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Test user's name")
    email: EmailStr = Field(..., description="Test user's email address")
    phone_number: str = Field(..., min_length=10, max_length=15, description="Test user's phone number")


class TestCredentialsResponse(BaseModel):
    success: bool
    message: str
    user_id: Optional[int] = None
