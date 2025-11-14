from .db import (
    get_db_connection, 
    initialize_database, 
    create_users_table,
    create_chat_histories_table,
    create_messages_table,
    create_default_chat_history,
    generate_random_conversation_name,
    create_test_user,
    create_support_tickets_table,
    create_support_ticket,
    get_all_support_tickets,
    update_support_ticket_status
)
from .models import (
    UserRequest, 
    UserResponse,
    MessageCreate,
    ChatHistoryCreate,
    MessageResponse,
    ChatHistoryResponse,
    ChatHistoryDetailResponse
)

__all__ = [
    "get_db_connection", 
    "initialize_database", 
    "create_users_table",
    "create_chat_histories_table",
    "create_messages_table",
    "create_default_chat_history",
    "generate_random_conversation_name",
    "create_test_user",
    "create_support_tickets_table",
    "create_support_ticket",
    "get_all_support_tickets",
    "update_support_ticket_status",
    "UserRequest", 
    "UserResponse",
    "MessageCreate",
    "ChatHistoryCreate",
    "MessageResponse",
    "ChatHistoryResponse",
    "ChatHistoryDetailResponse",
    "TestCredentialsRequest",
    "TestCredentialsResponse"
]

