# Frontend & Backend Integration Setup Guide

## Project Structure

\`\`\`
.
├── frontend/               # Next.js Frontend
│   ├── app/
│   ├── components/
│   ├── .env.local         # Frontend environment variables
│   ├── package.json
│   └── ...
├── backend/               # FastAPI Backend
│   ├── main.py           # Main application entry
│   ├── utils/
│   │   └── database.py   # Database utilities & models
│   ├── pyproject.toml    # Python dependencies
│   ├── requirements.txt  # Alternative dependencies file
│   └── database.db       # SQLite database (auto-created)
└── SETUP_GUIDE.md
\`\`\`

---

## Backend Setup (Python/FastAPI)

### Step 1: Install Python Dependencies

\`\`\`bash
cd backend

# Option A: Using pip
pip install -r requirements.txt

# Option B: Using poetry
pip install poetry
poetry install
\`\`\`

### Step 2: Run Backend Server

\`\`\`bash
python main.py
\`\`\`

Expected output:
\`\`\`
Uvicorn running on http://0.0.0.0:8000
INFO: Application startup complete
\`\`\`

The backend will:
- Create `database.db` automatically
- Initialize the database schema
- Create a test user (if not exists)
- Run on `http://localhost:8000`

### Test Backend with Sample Requests

\`\`\`bash
# Health check
curl http://localhost:8000/

# Test credentials validation
curl -X POST http://localhost:8000/test-credentials \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "phone_number": "9999999999"
  }'

# Create new user
curl -X POST http://localhost:8000/validate-users \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "phone_number": "9876543210"
  }'
\`\`\`

---

## Frontend Setup (Next.js)

### Step 1: Install Node Dependencies

\`\`\`bash
cd frontend

npm install
# or
yarn install
\`\`\`

### Step 2: Configure Backend URL

Edit `frontend/.env.local`:

\`\`\`
NEXT_PUBLIC_API_URL=http://localhost:8000
\`\`\`

### Step 3: Run Frontend Development Server

\`\`\`bash
npm run dev
# or
yarn dev
\`\`\`

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Testing the Integration

### Test Flow

1. **Start Backend** (Terminal 1):
   \`\`\`bash
   cd backend
   python main.py
   \`\`\`

2. **Start Frontend** (Terminal 2):
   \`\`\`bash
   cd frontend
   npm run dev
   \`\`\`

3. **Open Frontend**:
   - Go to http://localhost:3000

4. **Test Login**:
   - Option A: Use test user credentials
     - Name: Test User
     - Email: test@example.com
     - Phone: 9999999999
   - Option B: Register a new user
     - Fill in new details (email & phone must be unique)

5. **Test Chatbot**:
   - Type messages and watch them sync with backend
   - Create new chats
   - Delete chats
   - Upload files
   - All data persists in the backend database

---

## Common Issues & Solutions

### Issue: "Failed to fetch from backend"
- **Check**: Is backend running on port 8000?
- **Check**: Is `NEXT_PUBLIC_API_URL` correct in `.env.local`?
- **Fix**: Restart both servers

### Issue: "Email/Phone already exists"
- **Cause**: You tried to register with same email/phone
- **Fix**: Use different email/phone or use test credentials

### Issue: CORS errors
- **Check**: Backend CORS middleware is enabled
- **Status**: Already configured in `main.py` with `allow_origins=["*"]`

### Issue: Database locked
- **Cause**: Backend crashed while database was open
- **Fix**: Delete `backend/database.db` and restart

---

## API Endpoints Reference

### User Management
- `POST /validate-users` - Register new user
- `POST /test-credentials` - Validate test user

### Chat Management
- `GET /chat-histories/{user_id}` - Get user's chats
- `POST /chat-histories` - Create new chat
- `DELETE /chat-histories/{chat_history_id}` - Delete chat

### Messages
- `GET /chat-histories/{chat_history_id}/messages` - Get chat messages
- `POST /chat-histories/{chat_history_id}/messages` - Add message

---

## Production Deployment

### Backend (Python)
\`\`\`bash
# Use production ASGI server
pip install gunicorn
gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
\`\`\`

### Frontend (Next.js)
\`\`\`bash
npm run build
npm run start
\`\`\`

Update `.env.local` with production backend URL.

---

## File Descriptions

### Backend Files
- `main.py` - FastAPI app with all endpoints
- `utils/database.py` - SQLite database setup and Pydantic models
- `pyproject.toml` - Python package configuration
- `requirements.txt` - pip dependencies

### Frontend Files
- `app/page.tsx` - Main page routing login/chatbot
- `components/login-page.tsx` - Login UI with API calls
- `components/chatbot-page.tsx` - Chatbot UI with API integration
- `components/verification-form.tsx` - Form validation component
- `.env.local` - Environment configuration

---

## Need Help?

1. Check logs in both terminal windows
2. Verify ports (Backend: 8000, Frontend: 3000)
3. Check network tab in browser DevTools
4. Ensure Python 3.10+ and Node 16+ installed
