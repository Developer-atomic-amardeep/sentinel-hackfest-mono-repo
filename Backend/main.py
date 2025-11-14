import sqlite3
from typing import List
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from utils.database import get_db_connection, initialize_database, UserRequest, UserResponse
from utils.database import (
    get_db_connection, 
    initialize_database, 
    create_default_chat_history,
    generate_random_conversation_name,
    UserRequest, 
    UserResponse,
    MessageCreate,
    ChatHistoryCreate,
    MessageResponse,
    ChatHistoryResponse,
    ChatHistoryDetailResponse
)
from utils.database.models import (
    TestCredentialsRequest,
    TestCredentialsResponse
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database
    initialize_database()
    yield
    # Shutdown: (if needed, add cleanup code here)


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Server is running"}


@app.post("/validate-users", response_model=UserResponse)
def validate_users(user: UserRequest):
    """Validate and save user information to the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Collect all validation errors
        errors = []
        
        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email = ?", (user.email,))
        if cursor.fetchone():
            errors.append("Email already exists in the database")
        
        # Check if phone_number already exists
        cursor.execute("SELECT id FROM users WHERE phone_number = ?", (user.phone_number,))
        if cursor.fetchone():
            errors.append("Phone number already exists in the database")
        
        # If there are any errors, return them all at once
        if errors:
            raise HTTPException(status_code=400, detail=errors)
        
        # Insert user into database
        cursor.execute("""
            INSERT INTO users (name, email, phone_number)
            VALUES (?, ?, ?)
        """, (user.name, user.email, user.phone_number))
        
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        
        # Create default chat history with welcome message
        try:
            create_default_chat_history(user_id)
        except Exception as e:
            print(f"Warning: Failed to create default chat history: {e}")
        
        return UserResponse(
            id=user_id,
            name=user.name,
            email=user.email,
            phone_number=user.phone_number,
            message="User validated and saved successfully"
        )
    except HTTPException:
        # Re-raise HTTP exceptions (from duplicate checks)
        conn.rollback()
        raise
    except sqlite3.IntegrityError as e:
        conn.rollback()
        error_msg = str(e)
        errors = []
        if "UNIQUE constraint failed: users.email" in error_msg or "email" in error_msg.lower():
            errors.append("Email already exists in the database")
        if "UNIQUE constraint failed: users.phone_number" in error_msg or "phone_number" in error_msg.lower():
            errors.append("Phone number already exists in the database")
        
        if errors:
            raise HTTPException(status_code=400, detail=errors)
        raise HTTPException(status_code=400, detail=f"Database constraint error: {error_msg}")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        if conn:
            conn.close()


@app.post("/test-credentials", response_model=TestCredentialsResponse)
def validate_test_credentials(credentials: TestCredentialsRequest):
    """Validate test credentials against the permanent test user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Test user credentials (hardcoded for security)
        TEST_NAME = "Test User"
        TEST_EMAIL = "test@example.com"
        TEST_PHONE = "9999999999"
        
        # Validate credentials
        if (credentials.name == TEST_NAME and 
            credentials.email == TEST_EMAIL and 
            credentials.phone_number == TEST_PHONE):
            
            # Get test user ID
            cursor.execute("SELECT id FROM users WHERE email = ?", (TEST_EMAIL,))
            user_row = cursor.fetchone()
            
            if user_row:
                return TestCredentialsResponse(
                    success=True,
                    message="Test credentials validated successfully",
                    user_id=user_row[0]
                )
            else:
                raise HTTPException(
                    status_code=404, 
                    detail="Test user not found in database. Please restart the server to initialize test user."
                )
        else:
            return TestCredentialsResponse(
                success=False,
                message="Invalid test credentials. Please check name, email, and phone number."
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        conn.close()


@app.post("/chat-histories", response_model=ChatHistoryResponse)
def create_chat_history(chat_history: ChatHistoryCreate):
    """Create a new chat history/conversation for a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE id = ?", (chat_history.user_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")
        
        # Generate random but meaningful name if title not provided
        title = chat_history.title if chat_history.title else generate_random_conversation_name()
        
        # Create chat history
        cursor.execute("""
            INSERT INTO chat_histories (user_id, title)
            VALUES (?, ?)
        """, (chat_history.user_id, title))
        
        chat_history_id = cursor.lastrowid
        
        # Add welcome message from system
        cursor.execute("""
            INSERT INTO messages (chat_history_id, role, content)
            VALUES (?, 'system', 'Welcome to your new conversation! How can I assist you today?')
        """, (chat_history_id,))
        
        conn.commit()
        
        # Get the created record
        cursor.execute("""
            SELECT id, user_id, title, created_at
            FROM chat_histories
            WHERE id = ?
        """, (chat_history_id,))
        
        row = cursor.fetchone()
        
        return ChatHistoryResponse(
            id=row[0],
            user_id=row[1],
            title=row[2],
            created_at=row[3],
            message_count=1
        )
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        conn.close()


@app.get("/chat-histories/{user_id}", response_model=List[ChatHistoryResponse])
def get_user_chat_histories(user_id: int):
    """Get all chat histories for a specific user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get all chat histories with message count
        cursor.execute("""
            SELECT 
                ch.id, 
                ch.user_id, 
                ch.title, 
                ch.created_at,
                COUNT(m.id) as message_count
            FROM chat_histories ch
            LEFT JOIN messages m ON ch.id = m.chat_history_id
            WHERE ch.user_id = ?
            GROUP BY ch.id
            ORDER BY ch.created_at DESC
        """, (user_id,))
        
        rows = cursor.fetchall()
        
        chat_histories = [
            ChatHistoryResponse(
                id=row[0],
                user_id=row[1],
                title=row[2],
                created_at=row[3],
                message_count=row[4]
            )
            for row in rows
        ]
        
        return chat_histories
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        conn.close()


@app.get("/chat-histories/{chat_history_id}/messages", response_model=ChatHistoryDetailResponse)
def get_chat_history_messages(chat_history_id: int):
    """Get all messages for a specific chat history"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get chat history details
        cursor.execute("""
            SELECT id, user_id, title, created_at
            FROM chat_histories
            WHERE id = ?
        """, (chat_history_id,))
        
        chat_row = cursor.fetchone()
        if not chat_row:
            raise HTTPException(status_code=404, detail="Chat history not found")
        
        # Get all messages for this chat history
        cursor.execute("""
            SELECT id, chat_history_id, role, content, created_at
            FROM messages
            WHERE chat_history_id = ?
            ORDER BY created_at ASC
        """, (chat_history_id,))
        
        message_rows = cursor.fetchall()
        
        messages = [
            MessageResponse(
                id=row[0],
                chat_history_id=row[1],
                role=row[2],
                content=row[3],
                created_at=row[4]
            )
            for row in message_rows
        ]
        
        return ChatHistoryDetailResponse(
            id=chat_row[0],
            user_id=chat_row[1],
            title=chat_row[2],
            created_at=chat_row[3],
            messages=messages
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        conn.close()


@app.post("/chat-histories/{chat_history_id}/messages", response_model=MessageResponse)
def add_message_to_chat_history(chat_history_id: int, message: MessageCreate):
    """Add a new message to a chat history"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if chat history exists
        cursor.execute("SELECT id FROM chat_histories WHERE id = ?", (chat_history_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Chat history not found")
        
        # Insert message
        cursor.execute("""
            INSERT INTO messages (chat_history_id, role, content)
            VALUES (?, ?, ?)
        """, (chat_history_id, message.role, message.content))
        
        conn.commit()
        message_id = cursor.lastrowid
        
        # Get the created message
        cursor.execute("""
            SELECT id, chat_history_id, role, content, created_at
            FROM messages
            WHERE id = ?
        """, (message_id,))
        
        row = cursor.fetchone()
        
        return MessageResponse(
            id=row[0],
            chat_history_id=row[1],
            role=row[2],
            content=row[3],
            created_at=row[4]
        )
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        conn.close()


@app.delete("/chat-histories/{chat_history_id}")
def delete_chat_history(chat_history_id: int):
    """Delete a chat history and all its messages"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if chat history exists
        cursor.execute("SELECT id FROM chat_histories WHERE id = ?", (chat_history_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Chat history not found")
        
        # Delete chat history (messages will be deleted automatically via CASCADE)
        cursor.execute("DELETE FROM chat_histories WHERE id = ?", (chat_history_id,))
        
        conn.commit()
        
        return {"message": "Chat history deleted successfully", "chat_history_id": chat_history_id}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
