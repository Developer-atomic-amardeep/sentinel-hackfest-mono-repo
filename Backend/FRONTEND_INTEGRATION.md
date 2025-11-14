# Frontend Integration Guide

## Overview
This guide explains how to display the greeting message and final response from the backend AI agent system.

## API Endpoint
```
POST /query/stream
```

## Response Structure

The backend returns a **StreamingResponse** that streams state updates as Server-Sent Events (SSE). Each event contains a JSON object with the current state.

## Key Fields to Display

### 1. `greeting_message` (string | null)
- **When to show**: Immediately when query is received
- **Description**: Initial greeting shown to the user
- **Example**: `"Hello! We have received your query and are currently performing analysis in our system using our highly specialized AI agents. Please wait while we process your request..."`

### 2. `final_response` (string | null)
- **When to show**: After processing is complete
- **Description**: The complete answer to the user's query
- **Example**: `"Based on our payment policies, you can use credit cards, debit cards, or digital wallets like PayPal..."`

## Implementation Example

### JavaScript/TypeScript
```javascript
const response = await fetch('/query/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: userQuery })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

let greetingShown = false;

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  
  const chunk = decoder.decode(value);
  const lines = chunk.split('\n');
  
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.slice(6));
      
      // Display greeting message (once)
      if (data.greeting_message && !greetingShown) {
        displayGreeting(data.greeting_message);
        greetingShown = true;
      }
      
      // Display final response (when available)
      if (data.final_response) {
        displayFinalResponse(data.final_response);
      }
    }
  }
}
```

### React Example
```jsx
const [greeting, setGreeting] = useState(null);
const [finalResponse, setFinalResponse] = useState(null);

useEffect(() => {
  const eventSource = new EventSource(`/query/stream?query=${encodeURIComponent(userQuery)}`);
  
  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.greeting_message && !greeting) {
      setGreeting(data.greeting_message);
    }
    
    if (data.final_response) {
      setFinalResponse(data.final_response);
      eventSource.close();
    }
  };
  
  return () => eventSource.close();
}, [userQuery]);

// In your JSX:
return (
  <div>
    {greeting && <div className="greeting">{greeting}</div>}
    {finalResponse && <div className="response">{finalResponse}</div>}
  </div>
);
```

## UI Flow

1. **User submits query** → Show loading state
2. **Receive `greeting_message`** → Display greeting, keep loading indicator
3. **Receive `final_response`** → Display answer, hide loading indicator

## Optional: Progress Messages

You can also display intermediate progress by listening to other message fields:
- `supervisor_messages`: Overall orchestration status
- `general_information_messages`: Document retrieval progress
- `triage_messages`: Query analysis status

These are arrays of strings that show step-by-step progress.

## Error Handling

If the stream ends without a `final_response`, show an error message:
```javascript
if (!finalResponse) {
  displayError("Unable to process your query. Please try again.");
}
```

## Complete Flow Example

```
1. User Query: "What payment methods do you accept?"

2. Stream Update 1:
   {
     "greeting_message": "Hello! We have received your query...",
     "supervisor_messages": ["Received user query, routing to triage agent"],
     ...
   }
   → UI: Show greeting

3. Stream Update 2-5:
   {
     "general_information_messages": [
       "Step 1: Selecting relevant categories...",
       "Selected categories: Payment_Information",
       ...
     ],
     ...
   }
   → UI: Optionally show progress

4. Stream Update 6 (Final):
   {
     "final_response": "We accept the following payment methods...",
     ...
   }
   → UI: Show final answer, remove loading
```

## Summary

**Minimum Required Implementation:**
- Display `greeting_message` when it appears
- Display `final_response` when it appears
- Show loading state between the two

That's it! The backend handles all the complex AI orchestration.

