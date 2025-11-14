# Custom Streaming for Graph Visualization

## Overview

Custom streaming enables real-time visualization of the agent workflow by emitting progress updates **during** node execution, not just after completion. This allows you to build dynamic visualizations that show what's happening inside each agent as it processes.

## How It Works

### Two Types of Events

The streaming system emits two types of events:

1. **Progress Events** (`type: "progress"`) - Emitted **during** node execution
   - Shows what step the node is currently performing
   - Provides real-time updates as work progresses
   - Examples: "Calling API...", "Processing category 2/3...", "Generating SQL queries..."

2. **State Update Events** (`type: "state_update"`) - Emitted **after** node completion
   - Shows the final result when a node finishes
   - Contains the node's output and state changes
   - Triggers graph transitions to the next node

### Event Structure

All events follow a consistent structure that makes visualization straightforward:

```json
{
  "type": "progress" | "state_update",
  "node": "node_name",
  "user_query": "original user query",
  "message": "Human-readable description",
  "step": "step_identifier",
  // Additional context fields vary by node and step
}
```

**Progress Event Example:**
```json
{
  "type": "progress",
  "node": "general_information",
  "message": "Processing category 2/3: Payment_Information...",
  "step": "document_selection_category",
  "category": "Payment_Information",
  "progress": "2/3"
}
```

**State Update Event Example:**
```json
{
  "type": "state_update",
  "node": "triage",
  "triage_messages": ["..."],
  "intent": "technical_support",
  "sentiment": "neutral"
}
```

## Graph Visualization Flow

The streaming events enable you to visualize:

1. **Node Activation**: When a node starts executing (state_update)
2. **Internal Progress**: What the node is doing internally (progress events)
3. **Node Completion**: When a node finishes and what it produced (state_update)
4. **Graph Transitions**: How the workflow moves between nodes

### Example Visualization Sequence

```
[State Update] supervisor → Started
  ↓
[Progress] supervisor → "Received user query, routing to triage agent"
  ↓
[State Update] triage → Started
  ↓
[Progress] triage → "Calling DeepSeek API for classification..."
  ↓
[Progress] triage → "Parsing classification results..."
  ↓
[Progress] triage → "Classification complete - Intent: technical_support"
  ↓
[State Update] triage → Completed (intent, sentiment available)
  ↓
[State Update] supervisor → Routing decision made
  ↓
[Progress] supervisor → "Routing to general_information agent"
  ↓
[State Update] general_information → Started
  ↓
[Progress] general_information → "Step 1: Selecting relevant categories..."
  ↓
[Progress] general_information → "Selected categories: Payment_Information, Policies_&_Terms"
  ↓
[Progress] general_information → "Step 2: Selecting documents from 2 categories..."
  ↓
[Progress] general_information → "Processing category 1/2: Payment_Information..."
  ↓
[Progress] general_information → "Processing category 2/2: Policies_&_Terms..."
  ↓
[Progress] general_information → "Total documents selected: 5"
  ↓
[Progress] general_information → "Step 3: Generating final answer..."
  ↓
[Progress] general_information → "Response generated successfully"
  ↓
[State Update] general_information → Completed (final_response available)
```

## Flexibility for Dynamic Graphs

The streaming system is **graph-agnostic** and works with any workflow structure:

- **No Hardcoded Paths**: Events identify nodes by name, not by position
- **Dynamic Routing**: Works with conditional edges and dynamic routing decisions
- **Future-Proof**: Adding new nodes or changing the graph structure doesn't break visualization
- **Self-Describing**: Each event contains all necessary information (node name, step, context)

### How to Handle Graph Changes

When you modify the graph:

1. **Add New Nodes**: Just add progress events in the new node - visualization automatically picks them up
2. **Change Routing**: State updates show routing decisions dynamically - no code changes needed
3. **Modify Node Logic**: Progress events reflect internal steps - update events as needed
4. **Reorder Nodes**: Visualization follows the actual execution order automatically

## Implementation Details

### In Nodes

Nodes emit progress updates using `get_stream_writer()`:

```python
from langgraph.config import get_stream_writer

def my_node(state: AgentState) -> AgentState:
    writer = get_stream_writer()
    
    writer({
        "node": "my_node",
        "type": "progress",
        "message": "Starting step 1...",
        "step": "step1"
    })
    
    # Do work...
    
    writer({
        "node": "my_node",
        "type": "progress",
        "message": "Step 1 complete, starting step 2...",
        "step": "step2"
    })
    
    return {**state, "result": "done"}
```

### In Streaming Endpoint

The endpoint (`/analyze-query-stream`) streams both event types:

- Uses `stream_mode=["updates", "custom"]` to receive both progress and state updates
- Handles different chunk formats (dicts, tuples) for compatibility
- Emits Server-Sent Events (SSE) for real-time client updates

## Key Benefits for Visualization

1. **Real-Time Updates**: See progress as it happens, not just final results
2. **Granular Visibility**: Understand what each node is doing internally
3. **Dynamic Flow**: Visualization adapts to actual execution path automatically
4. **Context-Rich**: Each event includes relevant context (categories, counts, progress indicators)
5. **Error Resilient**: Invalid chunks are handled gracefully without breaking the stream

## Event Fields Reference

### Common Fields (All Events)
- `type`: `"progress"` or `"state_update"`
- `node`: Name of the node emitting the event
- `user_query`: Original user query
- `message`: Human-readable description

### Progress Event Fields
- `step`: Identifier for the current step (e.g., "api_call", "category_selection", "sql_generation")
- Additional fields vary by node and step (e.g., `category`, `progress`, `doc_count`, `subquery_count`)

### State Update Event Fields
- Node-specific message arrays (e.g., `triage_messages`, `general_information_messages`)
- Node outputs (e.g., `intent`, `sentiment`, `final_response`, `next_agent`)

## Summary

Custom streaming provides a **flexible, graph-agnostic** way to visualize agent workflows in real-time. By emitting progress events during execution and state updates on completion, you can build visualizations that dynamically adapt to any graph structure and show exactly what's happening inside each agent as it processes.
