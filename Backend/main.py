import json
import os
import sqlite3
import time
from typing import List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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
    ChatHistoryDetailResponse,
)
from utils.database.models import (
    TestCredentialsRequest,
    TestCredentialsResponse,
)
from agents.models import AnalyzeQueryRequest
from agents.graph import workflow

# Agora imports (token builder)
try:
    from agora_token_builder import RtcTokenBuilder
except ImportError:
    RtcTokenBuilder = None


# -------------------------------
#  LIFESPAN: INIT DATABASE
# -------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()   # creates DB + tables + test user
    yield


app = FastAPI(lifespan=lifespan)


# -------------------------------
#      CORS SETTINGS
# -------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # change this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------
#      BASIC HEALTH CHECK
# -------------------------------
@app.get("/")
def health_check():
    return {"status": "healthy", "message": "Server is running"}


@app.post("/analyze-query-stream")
def analyze_query_stream(request: AnalyzeQueryRequest):
    """
    Analyze a user query with streaming updates from the multi-agent workflow.
    
    This endpoint streams real-time updates as the workflow progresses through each node,
    allowing clients to see messages and state changes as they happen.
    
    Workflow: 
    1. Supervisor receives query
    2. Triage analyzes intent and sentiment
    3. Supervisor calls DeepSeek to determine routing
    4. Routes to: GeneralInformation | PersonalisedRAG | Escalation
    
    Stream format: Server-Sent Events (SSE) with JSON payloads
    
    Each event contains only relevant data for the executing node:
    - node: The node that was executed (always included)
    - user_query: The original user query (always included)
    
    Supervisor node returns:
    - supervisor_messages: Messages from supervisor
    - next_agent: Routing decision (when available)
    
    Triage node returns:
    - triage_messages: Messages from triage
    - intent: Classified intent
    - sentiment: Sentiment analysis
    - analysis: Detailed analysis
    
    General Information node returns:
    - general_information_messages: Messages from agent
    - final_response: Final response to user
    
    Personalised RAG node returns:
    - personalised_rag_messages: Messages from agent
    - final_response: Final response to user
    
    Escalation node returns:
    - escalation_messages: Messages from agent
    - final_response: Final response to user (with ticket details)
    """
    def generate_stream():
        try:
            # Initialize the state with all required fields from AgentState
            initial_state = {
                "user_query": request.user_query,
                "intent": None,
                "sentiment": None,
                "supervisor_messages": [],
                "triage_messages": [],
                "general_information_messages": [],
                "personalised_rag_messages": [],
                "escalation_messages": [],
                "analysis": None,
                "next_agent": None,
                "final_response": None
            }
            
            # Stream the workflow execution
            # stream_mode="updates" gives us state updates after each node
            for chunk in workflow.stream(initial_state, stream_mode="updates"):
                # chunk is a dict with node names as keys
                for node_name, state_update in chunk.items():
                    # Create a streaming event with only relevant data for the current node
                    event_data = {
                        "node": node_name,
                        "user_query": request.user_query
                    }
                    
                    # Add node-specific data based on which agent is executing
                    if node_name == "supervisor":
                        event_data["supervisor_messages"] = state_update.get("supervisor_messages", [])
                        # Include routing decision if available
                        if state_update.get("next_agent"):
                            event_data["next_agent"] = state_update.get("next_agent")
                    
                    elif node_name == "triage":
                        event_data["triage_messages"] = state_update.get("triage_messages", [])
                        # Include triage analysis results
                        if state_update.get("intent"):
                            event_data["intent"] = state_update.get("intent")
                        if state_update.get("sentiment"):
                            event_data["sentiment"] = state_update.get("sentiment")
                        if state_update.get("analysis"):
                            event_data["analysis"] = state_update.get("analysis")
                    
                    elif node_name == "general_information":
                        event_data["general_information_messages"] = state_update.get("general_information_messages", [])
                        # Include final response if available
                        if state_update.get("final_response"):
                            event_data["final_response"] = state_update.get("final_response")
                    
                    elif node_name == "personalised_rag":
                        event_data["personalised_rag_messages"] = state_update.get("personalised_rag_messages", [])
                        # Include final response if available
                        if state_update.get("final_response"):
                            event_data["final_response"] = state_update.get("final_response")
                    
                    elif node_name == "escalation":
                        event_data["escalation_messages"] = state_update.get("escalation_messages", [])
                        # Include final response if available
                        if state_update.get("final_response"):
                            event_data["final_response"] = state_update.get("final_response")
                    
                    # Format as Server-Sent Event
                    yield f"data: {json.dumps(event_data)}\n\n"
            
            # Send final completion event
            yield f"data: {json.dumps({'event': 'complete'})}\n\n"
        
        except ValueError as e:
            # Handle missing API key or configuration errors
            error_event = {
                "event": "error",
                "error": f"Configuration error: {str(e)}"
            }
            yield f"data: {json.dumps(error_event)}\n\n"
        
        except Exception as e:
            # Handle any other errors during workflow execution
            error_event = {
                "event": "error",
                "error": f"Error analyzing query: {str(e)}"
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering for nginx
        }
    )


# -------------------------------
#     VALIDATE + CREATE USER
# -------------------------------
@app.post("/validate-users", response_model=UserResponse)
def validate_users(user: UserRequest):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Check for duplicates
        errors = []

        cursor.execute("SELECT id FROM users WHERE email = ?", (user.email,))
        if cursor.fetchone():
            errors.append("Email already exists in the database")

        cursor.execute("SELECT id FROM users WHERE phone_number = ?", (user.phone_number,))
        if cursor.fetchone():
            errors.append("Phone number already exists in the database")

        if errors:
            raise HTTPException(status_code=400, detail=errors)

        # Insert user
        cursor.execute(
            """
            INSERT INTO users (name, email, phone_number)
            VALUES (?, ?, ?)
        """,
            (user.name, user.email, user.phone_number),
        )

        conn.commit()
        user_id = cursor.lastrowid
        conn.close()

        # Create default chat history
        try:
            create_default_chat_history(user_id)
        except:
            pass

        return UserResponse(
            id=user_id,
            name=user.name,
            email=user.email,
            phone_number=user.phone_number,
            message="User validated and saved successfully",
        )

    except HTTPException:
        conn.rollback()
        raise
    except sqlite3.IntegrityError as e:
        conn.rollback()
        msg = str(e)
        errors = []
        if "email" in msg.lower():
            errors.append("Email already exists in the database")
        if "phone" in msg.lower():
            errors.append("Phone number already exists in the database")

        if errors:
            raise HTTPException(status_code=400, detail=errors)

        raise HTTPException(status_code=400, detail=f"Database constraint error: {msg}")

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")

    finally:
        conn.close()


# -------------------------------
#     TEST CREDENTIALS LOGIN
# -------------------------------
@app.post("/test-credentials", response_model=TestCredentialsResponse)
def validate_test_credentials(credentials: TestCredentialsRequest):
    conn = get_db_connection()
    cursor = conn.cursor()

    TEST_NAME = "Test User"
    TEST_EMAIL = "test@example.com"
    TEST_PHONE = "9999999999"

    try:
        # Validate
        if (
            credentials.name == TEST_NAME
            and credentials.email == TEST_EMAIL
            and credentials.phone_number == TEST_PHONE
        ):
            cursor.execute("SELECT id FROM users WHERE email = ?", (TEST_EMAIL,))
            row = cursor.fetchone()

            if row:
                return TestCredentialsResponse(
                    success=True,
                    message="Test credentials validated successfully",
                    user_id=row[0],
                )
            else:
                raise HTTPException(
                    status_code=404,
                    detail="Test user not found in DB. Restart server to recreate test user.",
                )

        else:
            return TestCredentialsResponse(success=False, message="Invalid test credentials.")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
    finally:
        conn.close()


# -------------------------------
#     CREATE CHAT HISTORY
# -------------------------------
@app.post("/chat-histories", response_model=ChatHistoryResponse)
def create_chat_history(chat_history: ChatHistoryCreate):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM users WHERE id = ?", (chat_history.user_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")

        title = (
            chat_history.title
            if chat_history.title
            else generate_random_conversation_name()
        )

        cursor.execute(
            """
            INSERT INTO chat_histories (user_id, title)
            VALUES (?, ?)
        """,
            (chat_history.user_id, title),
        )

        chat_history_id = cursor.lastrowid

        # Add welcome message
        cursor.execute(
            """
            INSERT INTO messages (chat_history_id, role, content)
            VALUES (?, 'system', 'Welcome to your new conversation! How can I assist you today?')
        """,
            (chat_history_id,),
        )

        conn.commit()

        cursor.execute(
            """
            SELECT id, user_id, title, created_at
            FROM chat_histories
            WHERE id = ?
        """,
            (chat_history_id,),
        )
        row = cursor.fetchone()

        return ChatHistoryResponse(
            id=row[0],
            user_id=row[1],
            title=row[2],
            created_at=row[3],
            message_count=1,
        )

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
    finally:
        conn.close()


# -------------------------------
#     GET ALL CHAT HISTORIES
# -------------------------------
@app.get("/chat-histories/{user_id}", response_model=List[ChatHistoryResponse])
def get_user_chat_histories(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")

        cursor.execute(
            """
            SELECT ch.id, ch.user_id, ch.title, ch.created_at,
                   COUNT(m.id) as message_count
            FROM chat_histories ch
            LEFT JOIN messages m ON ch.id = m.chat_history_id
            WHERE ch.user_id = ?
            GROUP BY ch.id
            ORDER BY ch.created_at DESC
        """,
            (user_id,),
        )

        rows = cursor.fetchall()

        return [
            ChatHistoryResponse(
                id=row[0],
                user_id=row[1],
                title=row[2],
                created_at=row[3],
                message_count=row[4],
            )
            for row in rows
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")

    finally:
        conn.close()


# -------------------------------
#   GET MESSAGES OF A CHAT
# -------------------------------
@app.get("/chat-histories/{chat_history_id}/messages", response_model=ChatHistoryDetailResponse)
def get_chat_history_messages(chat_history_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT id, user_id, title, created_at
            FROM chat_histories
            WHERE id = ?
        """,
            (chat_history_id,),
        )
        chat = cursor.fetchone()

        if not chat:
            raise HTTPException(status_code=404, detail="Chat history not found")

        cursor.execute(
            """
            SELECT id, chat_history_id, role, content, created_at
            FROM messages
            WHERE chat_history_id = ?
            ORDER BY created_at ASC
        """,
            (chat_history_id,),
        )
        rows = cursor.fetchall()

        messages = [
            MessageResponse(
                id=row[0],
                chat_history_id=row[1],
                role=row[2],
                content=row[3],
                created_at=row[4],
            )
            for row in rows
        ]

        return ChatHistoryDetailResponse(
            id=chat[0],
            user_id=chat[1],
            title=chat[2],
            created_at=chat[3],
            messages=messages,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
    finally:
        conn.close()


# -------------------------------
#     ADD MESSAGE TO CHAT
# -------------------------------
@app.post("/chat-histories/{chat_history_id}/messages", response_model=MessageResponse)
def add_message_to_chat_history(chat_history_id: int, message: MessageCreate):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM chat_histories WHERE id = ?", (chat_history_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Chat history not found")

        cursor.execute(
            """
            INSERT INTO messages (chat_history_id, role, content)
            VALUES (?, ?, ?)
        """,
            (chat_history_id, message.role, message.content),
        )

        conn.commit()
        msg_id = cursor.lastrowid

        cursor.execute(
            """
            SELECT id, chat_history_id, role, content, created_at
            FROM messages
            WHERE id = ?
        """,
            (msg_id,),
        )
        row = cursor.fetchone()

        return MessageResponse(
            id=row[0],
            chat_history_id=row[1],
            role=row[2],
            content=row[3],
            created_at=row[4],
        )

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
    finally:
        conn.close()


# -------------------------------
#        DELETE CHAT
# -------------------------------
@app.delete("/chat-histories/{chat_history_id}")
def delete_chat_history(chat_history_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM chat_histories WHERE id = ?", (chat_history_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Chat history not found")

        cursor.execute("DELETE FROM chat_histories WHERE id = ?", (chat_history_id,))
        conn.commit()

        return {"message": "Chat history deleted successfully", "chat_history_id": chat_history_id}

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")

    finally:
        conn.close()


# -------------------------------
#       AGORA TOKEN ENDPOINT
# -------------------------------
AGORA_APP_ID = os.environ.get("AGORA_APP_ID", "2a6956e71fb8440fa02280fe095709f7")
AGORA_APP_CERTIFICATE = os.environ.get("AGORA_APP_CERTIFICATE", "1bab8c6d85ae4920940333fe801779cb")

@app.get("/agora-token")
def generate_agora_token(
    channel: str = Query(...),
    uid: int = Query(0),
    expire_seconds: int = Query(3600)
):
    if RtcTokenBuilder is None:
        raise HTTPException(status_code=500, detail="agora-token-builder not installed")

    try:
        current_ts = int(time.time())
        expire_ts = current_ts + int(expire_seconds)

        role = 1  # publisher

        token = RtcTokenBuilder.buildTokenWithUid(
            AGORA_APP_ID,
            AGORA_APP_CERTIFICATE,
            channel,
            uid,
            role,
            expire_ts,
        )

        return {
            "appId": AGORA_APP_ID,
            "token": token,
            "channel": channel,
            "uid": uid,
            "expires_at": expire_ts,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate token: {e}")


# -------------------------------
#     RUN SERVER DIRECTLY
# -------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
