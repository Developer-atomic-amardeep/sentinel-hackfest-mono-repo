# Escalation System - Demo Guide

## Overview
The escalation system automatically detects queries that require human intervention and creates support tickets in SQLite database for human agents to review and resolve.

## What Was Implemented

### 1. Enhanced Supervisor Routing
The supervisor now intelligently routes queries to escalation based on these categories:
- **Disputes and Complaints**: Product quality, service issues, billing disputes, compensation requests
- **Returns & Refunds Beyond Policy**: Late returns, missing receipts, partial refunds
- **Fraud Detection**: Suspicious orders, fraudulent transactions, account takeover
- **Complex Technical Issues**: System bugs, data corruption, integration problems
- **Payment Problems**: Payment failures, chargebacks, verification issues

### 2. Database Schema
**Support Tickets Table** (`support_tickets`):
- `ticket_id`: Unique ID (e.g., TKT-ABC12345)
- `user_query`: Original user complaint/query
- `intent`: Classified intent from triage
- `sentiment`: Sentiment classification (negative → high priority)
- `priority`: low, medium, high, urgent (auto-determined)
- `status`: open, in_progress, resolved, closed
- `category`: Auto-categorized (Returns & Refunds, Payment Issues, etc.)
- `assigned_to`: Agent assigned to ticket
- `resolution_notes`: Notes about resolution
- Timestamps: `created_at`, `updated_at`, `resolved_at`

### 3. API Endpoints

#### GET `/support-tickets`
View all support tickets (human agent dashboard)
```bash
# Get all tickets
curl http://localhost:8000/support-tickets

# Get only open tickets
curl http://localhost:8000/support-tickets?status=open

# Get in-progress tickets
curl http://localhost:8000/support-tickets?status=in_progress
```

#### GET `/support-tickets/{ticket_id}`
View a specific ticket
```bash
curl http://localhost:8000/support-tickets/TKT-ABC12345
```

#### PUT `/support-tickets/{ticket_id}`
Update ticket status (human agent action)
```bash
# Mark as in progress
curl -X PUT "http://localhost:8000/support-tickets/TKT-ABC12345?status=in_progress&assigned_to=John%20Doe"

# Mark as resolved
curl -X PUT "http://localhost:8000/support-tickets/TKT-ABC12345?status=resolved&resolution_notes=Refund%20processed"

# Close ticket
curl -X PUT "http://localhost:8000/support-tickets/TKT-ABC12345?status=closed"
```

## Demo Flow for Hackathon

### Step 1: Trigger Escalation
Send queries that match escalation criteria:

**Example 1: Refund Beyond Policy**
```json
{
  "query": "I want a refund for an item I bought 6 months ago, it's broken"
}
```

**Example 2: Billing Dispute**
```json
{
  "query": "I was charged twice for the same order, this is unacceptable!"
}
```

**Example 3: Fraud Alert**
```json
{
  "query": "There are suspicious transactions on my account that I didn't make"
}
```

**Example 4: Delivery Issue**
```json
{
  "query": "My package was damaged during delivery and some items are missing"
}
```

**Example 5: Technical Issue**
```json
{
  "query": "The website keeps crashing when I try to checkout, I've lost my cart 3 times"
}
```

### Step 2: Show Ticket Creation
The system will:
1. Route to escalation_node (supervisor detects it matches escalation criteria)
2. Create ticket in database
3. Return ticket ID to user (e.g., TKT-ABC12345)
4. Assign priority based on sentiment (negative = high priority)
5. Auto-categorize the issue

User sees response like:
```
Thank you for reaching out. Your issue has been escalated to our human support team.

**Ticket Details:**
- **Ticket ID**: TKT-A1B2C3D4
- **Status**: Open
- **Priority**: High
- **Category**: Returns & Refunds
- **Sentiment**: Negative

Due to the nature of your issue, we've marked this as a high-priority ticket.
A support agent will review your case and contact you shortly.
```

### Step 3: View Ticket Queue (Human Agent View)
Open in browser or Postman:
```
GET http://localhost:8000/support-tickets
```

Shows all escalated tickets with details:
```json
{
  "success": true,
  "count": 5,
  "tickets": [
    {
      "id": 1,
      "ticket_id": "TKT-A1B2C3D4",
      "user_query": "I want a refund for an item I bought 6 months ago, it's broken",
      "intent": "refund_request",
      "sentiment": "negative",
      "priority": "high",
      "status": "open",
      "category": "Returns & Refunds",
      "created_at": "2025-11-14T10:30:00"
    }
  ]
}
```

### Step 4: Human Agent Takes Action
Update ticket status as human agent works on it:

```bash
# Agent starts working on ticket
curl -X PUT "http://localhost:8000/support-tickets/TKT-A1B2C3D4?status=in_progress&assigned_to=Sarah%20Johnson"

# Agent resolves the ticket
curl -X PUT "http://localhost:8000/support-tickets/TKT-A1B2C3D4?status=resolved&resolution_notes=Processed%20refund%20and%20issued%20store%20credit"
```

### Step 5: Show Final Status
```
GET http://localhost:8000/support-tickets/TKT-A1B2C3D4
```

Shows updated ticket:
```json
{
  "success": true,
  "ticket": {
    "ticket_id": "TKT-A1B2C3D4",
    "status": "resolved",
    "assigned_to": "Sarah Johnson",
    "resolution_notes": "Processed refund and issued store credit",
    "resolved_at": "2025-11-14T11:15:00"
  }
}
```

## Demo Talking Points

### For Judges:
1. **Intelligent Detection**: "The system automatically detects when a query requires human judgment"
2. **Real Database**: "Tickets are stored in SQLite, ready for integration with real ticketing systems"
3. **Priority Assignment**: "Negative sentiment automatically creates high-priority tickets"
4. **Full Tracking**: "Every ticket has timestamps, status, priority, and category"
5. **Human-in-the-Loop**: "Clear handoff from AI to human with full context"

### Technical Highlights:
- Supervisor uses enhanced LLM prompt with specific escalation criteria
- Auto-categorization based on query content
- Priority based on sentiment analysis
- RESTful API for human agent dashboard
- SQLite for quick demo (easily replaceable with PostgreSQL/MongoDB)

## Quick Test Script

```bash
# 1. Start the server
cd Backend
python main.py

# 2. Send escalation query
curl -X POST http://localhost:8000/analyze-query-stream \
  -H "Content-Type: application/json" \
  -d '{"query": "I was charged twice and want a refund immediately!"}'

# 3. View all tickets
curl http://localhost:8000/support-tickets

# 4. Update a ticket (replace TICKET_ID with actual ID)
curl -X PUT "http://localhost:8000/support-tickets/TKT-ABC12345?status=in_progress&assigned_to=Demo%20Agent"
```

## Visual Demo Suggestions

1. **Split Screen**:
   - Left: User chat interface (trigger escalation)
   - Right: Support ticket dashboard (show ticket appearing)

2. **Browser Tabs**:
   - Tab 1: User interface sending query
   - Tab 2: `/support-tickets` endpoint showing ticket queue
   - Tab 3: Swagger/API docs showing endpoints

3. **Terminal Demo**:
   - Window 1: Server logs (showing ticket creation)
   - Window 2: curl commands (sending queries)
   - Window 3: Database viewer (showing tickets table)

## Integration Ready

The system is ready to integrate with:
- Zendesk, Freshdesk, or custom ticketing systems
- Email notifications (SMTP integration point identified)
- WebSocket for real-time ticket updates
- Admin dashboard (React/Vue frontend)
- User portal (ticket status lookup)

## Next Steps (Post-Hackathon)

1. Add email notifications when ticket is created/updated
2. Add WebSocket for real-time dashboard updates
3. Create React dashboard for human agents
4. Add file attachment support for tickets
5. Implement SLA tracking (response time, resolution time)
6. Add ticket history/audit log

