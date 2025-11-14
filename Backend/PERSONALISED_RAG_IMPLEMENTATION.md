# Personalised RAG Node Implementation

## Overview
The `personalised_rag_node` has been implemented with a sophisticated multi-step RAG (Retrieval-Augmented Generation) approach that handles user queries about personal data from CSV files stored in SQLite database.

## Architecture Flow

### Step 1: Database Setup
- Automatically loads CSV data from `data/personalised_agent/*.csv` into SQLite tables
- Creates tables if they don't exist
- Uses the following tables:
  - `user_info` - User account information
  - `orders` - Order history and details
  - `order_items` - Individual items in each order
  - `transactions` - Payment transaction records
  - `cart` - Current shopping cart items
  - `addresses` - Saved addresses
  - `returns` - Return/refund requests

### Step 2: Schema Loading
- Extracts table schemas (column names) from CSV files
- Formats schema information for LLM context

### Step 3: Subquery Generation
- Uses DeepSeek LLM to analyze the user query
- Generates 1-5 simple, focused subqueries
- Each subquery is designed to be easily convertible to SQL
- Context includes all table schemas to help LLM understand available data

### Step 4: Parallel SQL Generation
- Uses `asyncio` to generate SQL queries from subqueries in parallel
- Each subquery is sent to DeepSeek with table schema context
- LLM generates SQLite-compatible SQL queries
- Handles errors gracefully, filtering out failed generations

### Step 5: Parallel SQL Execution
- Uses `asyncio` to execute all SQL queries in parallel on the SQLite database
- Each query runs in a thread pool executor to avoid blocking
- Results are collected and aggregated
- Error handling for each query execution

### Step 6: Final Answer Generation
- Aggregates all query results
- Formats results as context for the final LLM call
- Uses DeepSeek to generate a natural language answer
- Answer is personalized, friendly, and easy to understand

## Key Features

### 🚀 Performance Optimizations
- **Parallel Processing**: SQL generation and execution happen concurrently using `asyncio`
- **Efficient Database Access**: Uses connection pooling and prepared statements
- **Smart Caching**: Checks if tables already exist before reloading CSV data

### 🛡️ Error Handling
- Graceful degradation if some SQL queries fail
- Detailed error messages for debugging
- Fallback responses for users if processing fails
- Validates generated SQL before execution

### 🎯 Simplicity
- Follows the principle of keeping workflows simple
- Each subquery is designed to be straightforward
- SQL queries are kept simple and efficient
- Clear separation of concerns with helper functions

### 📊 Database Management
- Automatic CSV to SQLite conversion
- Dynamic table creation based on CSV headers
- All columns stored as TEXT for flexibility
- Row-factory enabled for easy dictionary access

## Implementation Details

### New Functions

1. **`get_table_schemas()`**
   - Reads CSV files to extract column headers
   - Returns dictionary mapping table names to column lists

2. **`format_table_schemas()`**
   - Formats schema information for LLM consumption
   - Creates readable string representation

3. **`generate_sql_from_subquery()` (async)**
   - Converts natural language subquery to SQL
   - Uses DeepSeek with low temperature (0.1) for consistency
   - Returns SQL query with error information

4. **`execute_sql_query()` (async)**
   - Executes SQL query on SQLite database
   - Runs in thread pool to avoid blocking
   - Returns results as list of dictionaries

5. **`load_csv_data_to_db()`**
   - Loads CSV files into SQLite tables
   - Checks if tables already exist to avoid reloading
   - Creates tables dynamically based on CSV headers

6. **`personalised_rag_node()` (main function)**
   - Orchestrates the entire RAG pipeline
   - Integrates all steps into a cohesive workflow
   - Returns updated agent state with final response

### New Prompts

1. **`SUBQUERY_GENERATION_PROMPT`**
   - Guides LLM to decompose user queries into subqueries
   - Provides table schema context
   - Enforces max 5 subqueries limit

2. **`SQL_GENERATION_PROMPT`**
   - Guides LLM to generate SQLite SQL queries
   - Ensures proper syntax and table/column names
   - Focuses on executable, simple queries

3. **`PERSONALIZED_FINAL_ANSWER_PROMPT`**
   - Guides LLM to generate user-friendly answers
   - Emphasizes personalization and clarity
   - Handles data formatting (dates, currency, etc.)

## Usage Example

```python
# User query
state = {
    "user_query": "What is the status of my recent orders?",
    "personalised_rag_messages": []
}

# Process through personalised_rag_node
result = personalised_rag_node(state)

# Result contains:
# - personalised_rag_messages: List of processing steps
# - final_response: Natural language answer with order details
```

## Testing

To test the implementation:

1. Ensure CSV files are in `Backend/data/personalised_agent/`
2. Set up DeepSeek API key in environment
3. Run a query through the agent system
4. Check `personalised_rag_messages` for detailed logs
5. Verify final response is accurate and personalized

## Future Enhancements

Potential improvements:
- Add query result caching for frequently asked questions
- Implement more sophisticated SQL optimization
- Add support for aggregate queries and analytics
- Include query history for context-aware responses
- Add user authentication to filter data by user_id

## Dependencies

- `asyncio` - For parallel processing
- `sqlite3` - Database operations
- `csv` - CSV file parsing
- `pathlib` - Path operations
- DeepSeek API - LLM inference
- `json` - JSON parsing

## Notes

- All SQL queries are generated by LLM, so results depend on DeepSeek's capability
- Database is automatically populated from CSV files on first run
- Maximum 5 subqueries to prevent excessive API calls
- Error messages are user-friendly while maintaining debugging information

