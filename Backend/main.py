import json
import os
import sqlite3
import time
import shutil
from typing import List, Optional
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Local imports
from utils.database import (
    get_db_connection,
    initialize_database,
    create_default_chat_history,
    generate_random_conversation_name,
    get_all_support_tickets,
    update_support_ticket_status,
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
#  FILE UPLOAD CONFIGURATION
# -------------------------------
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.txt', '.png', '.jpg', '.jpeg', '.gif', '.webp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# -------------------------------
#  ENHANCED REQUEST MODEL
# -------------------------------
class AnalyzeQueryRequestWithFiles(BaseModel):
    user_query: str
    file_paths: Optional[List[str]] = []


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


# -------------------------------
#      FILE UPLOAD ENDPOINT
# -------------------------------
@app.post("/upload-files")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Upload multiple files and return their paths.
    
    Accepts: PDF, DOC, DOCX, TXT, PNG, JPG, JPEG, GIF, WEBP
    Max size per file: 10 MB
    
    Returns:
        {
            "success": true,
            "file_paths": ["uploads/file1.pdf", "uploads/file2.png"],
            "files_info": [
                {"name": "file1.pdf", "size": 12345, "path": "uploads/file1.pdf"},
                ...
            ]
        }
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    uploaded_files = []
    file_paths = []
    
    for file in files:
        # Validate file extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"File type {file_ext} not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        # Validate file size
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File {file.filename} exceeds maximum size of {MAX_FILE_SIZE / (1024*1024)} MB"
            )
        
        # Generate unique filename
        timestamp = int(time.time() * 1000)
        safe_filename = f"{timestamp}_{file.filename}"
        file_path = UPLOAD_DIR / safe_filename
        
        # Save file
        try:
            with open(file_path, "wb") as f:
                f.write(content)
            
            uploaded_files.append({
                "name": file.filename,
                "size": file_size,
                "path": str(file_path)
            })
            file_paths.append(str(file_path))
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save file {file.filename}: {str(e)}"
            )
    
    return {
        "success": True,
        "file_paths": file_paths,
        "files_info": uploaded_files
    }


# -------------------------------
#   HELPER: EXTRACT FILE CONTENT
# -------------------------------
def extract_file_content(file_path: str) -> str:
    """
    Extract text content from uploaded files.
    
    For images: returns file name and type
    For text/PDF/docs: attempts to extract text content
    """
    try:
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            return f"[File not found: {file_path}]"
        
        file_ext = file_path_obj.suffix.lower()
        
        # Handle text files
        if file_ext == '.txt':
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                return f"[Text file: {file_path_obj.name}]\n{content[:5000]}"  # Limit to 5000 chars
        
        # Handle images (just return metadata)
        elif file_ext in {'.png', '.jpg', '.jpeg', '.gif', '.webp'}:
            file_size = file_path_obj.stat().st_size
            return f"[Image file: {file_path_obj.name}, Size: {file_size} bytes]"
        
        # Handle PDF files (requires PyPDF2 or similar)
        elif file_ext == '.pdf':
            try:
                import PyPDF2
                with open(file_path, 'rb') as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    text = ""
                    for page_num in range(min(10, len(pdf_reader.pages))):  # First 10 pages
                        text += pdf_reader.pages[page_num].extract_text()
                    return f"[PDF file: {file_path_obj.name}]\n{text[:5000]}"
            except ImportError:
                return f"[PDF file: {file_path_obj.name}] (PDF parsing not available - install PyPDF2)"
            except Exception as e:
                return f"[PDF file: {file_path_obj.name}] (Error reading: {str(e)})"
        
        # Handle Word documents (requires python-docx)
        elif file_ext in {'.doc', '.docx'}:
            try:
                import docx
                doc = docx.Document(file_path)
                text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
                return f"[Word document: {file_path_obj.name}]\n{text[:5000]}"
            except ImportError:
                return f"[Word document: {file_path_obj.name}] (DOCX parsing not available - install python-docx)"
            except Exception as e:
                return f"[Word document: {file_path_obj.name}] (Error reading: {str(e)})"
        
        else:
            return f"[Unsupported file type: {file_path_obj.name}]"
            
    except Exception as e:
        return f"[Error processing file: {str(e)}]"


# -------------------------------
#   ANALYZE QUERY WITH FILES
# -------------------------------
@app.post("/analyze-query-stream")
def analyze_query_stream(request: AnalyzeQueryRequestWithFiles):
    """
    Analyze a user query with streaming updates from the multi-agent workflow.
    Now supports file uploads - files are processed and their content is included in the analysis.
    
    This endpoint streams real-time updates as the workflow progresses through each node,
    allowing clients to see messages and state changes as they happen.
    
    Request body:
    {
        "user_query": "What is my flight status?",
        "file_paths": ["uploads/ticket.pdf", "uploads/booking.png"]  // Optional
    }
    
    Workflow: 
    1. Supervisor receives query (with file context if provided)
    2. Triage analyzes intent and sentiment
    3. Supervisor calls DeepSeek to determine routing
    4. Routes to: GeneralInformation | PersonalisedRAG | Escalation
    
    Stream format: Server-Sent Events (SSE) with JSON payloads
    """
    def generate_stream():
        try:
            # Process uploaded files if any
            file_context = ""
            if request.file_paths:
                file_contents = []
                for file_path in request.file_paths:
                    content = extract_file_content(file_path)
                    file_contents.append(content)
                
                if file_contents:
                    file_context = "\n\n--- UPLOADED FILES ---\n" + "\n\n".join(file_contents) + "\n--- END OF FILES ---\n\n"
            
            # Enhance user query with file context
            enhanced_query = request.user_query
            if file_context:
                enhanced_query = f"{request.user_query}\n\n{file_context}"
            
            # Initialize the state with all required fields from AgentState
            initial_state = {
                "user_query": enhanced_query,  # Include file content in query
                "intent": None,
                "sentiment": None,
                "supervisor_messages": [],
                "triage_messages": [],
                "general_information_messages": [],
                "personalised_rag_messages": [],
                "escalation_messages": [],
                "analysis": None,
                "next_agent": None,
                "final_response": None,
                "greeting_message": None
            }
            
            # Stream the workflow execution
            # stream_mode=["updates", "custom"] gives us both state updates after each node
            # AND custom progress updates from within nodes while they're running
            for chunk in workflow.stream(initial_state, stream_mode=["updates", "custom"]):
                try:
                    # Handle tuple format: (mode, data) - sometimes LangGraph returns tuples
                    if isinstance(chunk, tuple) and len(chunk) == 2:
                        mode, data = chunk
                        # Process based on mode
                        if mode == "custom" and isinstance(data, dict):
                            # Custom progress event
                            event_data = {
                                "type": "progress",
                                "user_query": request.user_query,
                                **data
                            }
                            yield f"data: {json.dumps(event_data)}\n\n"
                            continue
                        elif mode == "updates" and isinstance(data, dict):
                            chunk = data  # Use the data part as chunk
                        else:
                            continue
                    
                    # Skip non-dict chunks
                    if not isinstance(chunk, dict):
                        continue
                    
                    # Check if this is a custom streaming event (has "type": "progress" or "node" key)
                    # Custom events from get_stream_writer() will have the structure we defined in nodes
                    is_custom_event = False
                    custom_data = None
                    
                    # Check if this looks like a custom progress event
                    # Custom events have "type": "progress" and "node" keys
                    if chunk.get("type") == "progress" or ("node" in chunk and "step" in chunk):
                        is_custom_event = True
                        custom_data = chunk
                    # Also check for LangGraph's custom event format
                    elif "__custom__" in chunk:
                        custom_data = chunk.get("__custom__")
                        if isinstance(custom_data, dict):
                            is_custom_event = True
                    
                    if is_custom_event and custom_data:
                        # Custom data emitted from within nodes (progress updates)
                        event_data = {
                            "type": "progress",
                            "user_query": request.user_query,
                            **custom_data  # Include all custom data (node, message, step, etc.)
                        }
                        yield f"data: {json.dumps(event_data)}\n\n"
                    
                    else:
                        # Handle state updates (after node completion)
                        # chunk is a dict with node names as keys
                        if not hasattr(chunk, 'items'):
                            continue
                            
                        for node_name, state_update in chunk.items():
                            # Skip internal LangGraph keys
                            if node_name.startswith("__"):
                                continue
                            
                            # Ensure state_update is a dict
                            if not isinstance(state_update, dict):
                                continue
                                
                            # Create a streaming event with only relevant data for the current node
                            event_data = {
                                "type": "state_update",
                                "node": node_name,
                                "user_query": request.user_query  # Send original query (without file content)
                            }
                            
                            # Add node-specific data based on which agent is executing
                            if node_name == "supervisor":
                                event_data["supervisor_messages"] = state_update.get("supervisor_messages", [])
                                # Include greeting message if available
                                if state_update.get("greeting_message"):
                                    event_data["greeting_message"] = state_update.get("greeting_message")
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
                
                except Exception as chunk_error:
                    # Log chunk processing errors but don't break the stream
                    # This helps debug issues with specific chunk formats
                    error_event = {
                        "type": "error",
                        "message": f"Error processing chunk: {str(chunk_error)}",
                        "chunk_type": str(type(chunk).__name__)
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                    continue
            
            # Send final completion event
            yield f"data: {json.dumps({'event': 'complete'})}\n\n"
        
        except ValueError as e:
            error_event = {
                "event": "error",
                "error": f"Configuration error: {str(e)}"
            }
            yield f"data: {json.dumps(error_event)}\n\n"
        
        except Exception as e:
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
            "X-Accel-Buffering": "no"
        }
    )


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

        # REMOVED: No longer adding welcome message to database
        # Users will see a clean empty chat

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
            message_count=0,  # Changed from 1 to 0
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
#     SUPPORT TICKETS ENDPOINTS
# -------------------------------
@app.get("/support-tickets")
def get_support_tickets(status: str = Query(None, description="Filter by status: open, in_progress, resolved, closed")):
    """
    Get all support tickets, optionally filtered by status.
    
    This endpoint is used by human agents to view escalated tickets.
    
    Query Parameters:
    - status (optional): Filter tickets by status (open, in_progress, resolved, closed)
    
    Returns:
    - List of support tickets with all details
    """
    try:
        tickets = get_all_support_tickets(status_filter=status)
        
        return {
            "success": True,
            "count": len(tickets),
            "tickets": tickets
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve tickets: {str(e)}")


@app.put("/support-tickets/{ticket_id}")
def update_ticket_status(
    ticket_id: str,
    status: str = Query(..., description="New status: open, in_progress, resolved, closed"),
    assigned_to: str = Query(None, description="Agent assigned to ticket"),
    resolution_notes: str = Query(None, description="Notes about resolution")
):
    """
    Update the status of a support ticket.
    
    This endpoint is used by human agents to update ticket status as they work on them.
    
    Path Parameters:
    - ticket_id: The unique ticket ID (e.g., TKT-ABC12345)
    
    Query Parameters:
    - status (required): New status (open, in_progress, resolved, closed)
    - assigned_to (optional): Name of agent assigned to the ticket
    - resolution_notes (optional): Notes about the resolution
    
    Returns:
    - Updated ticket details
    """
    try:
        # Validate status
        valid_statuses = ["open", "in_progress", "resolved", "closed"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        
        updated_ticket = update_support_ticket_status(
            ticket_id=ticket_id,
            status=status,
            assigned_to=assigned_to,
            resolution_notes=resolution_notes
        )
        
        return {
            "success": True,
            "message": f"Ticket {ticket_id} updated successfully",
            "ticket": updated_ticket
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update ticket: {str(e)}")


@app.get("/support-tickets/{ticket_id}")
def get_ticket_by_id(ticket_id: str):
    """
    Get a specific support ticket by ID.
    
    Path Parameters:
    - ticket_id: The unique ticket ID (e.g., TKT-ABC12345)
    
    Returns:
    - Ticket details
    """
    try:
        # Get all tickets and filter by ID
        all_tickets = get_all_support_tickets()
        ticket = next((t for t in all_tickets if t["ticket_id"] == ticket_id), None)
        
        if not ticket:
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
        
        return {
            "success": True,
            "ticket": ticket
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve ticket: {str(e)}")


# -------------------------------
#     RUN SERVER DIRECTLY
# -------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9000)