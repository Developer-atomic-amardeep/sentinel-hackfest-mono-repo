import json
import os
import asyncio
import sqlite3
import csv
from typing import List, Dict, Any
from pathlib import Path
from agents.states import AgentState
from agents.utils import call_deepseek_chat
from agents.prompts import (
    TRIAGE_PROMPT, 
    SUPERVISOR_ROUTING_PROMPT,
    CATEGORY_SELECTION_PROMPT,
    DOCUMENT_SELECTION_PROMPT,
    FINAL_ANSWER_PROMPT,
    SUBQUERY_GENERATION_PROMPT,
    SQL_GENERATION_PROMPT,
    PERSONALIZED_FINAL_ANSWER_PROMPT
)

def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor agent node - orchestrates the workflow.
    Receives user queries and coordinates with other agents.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state
    """
    supervisor_messages = state.get("supervisor_messages", [])
    
    # Log supervisor activity
    if not state.get("intent"):
        # Initial pass - supervisor receives the query
        greeting_message = "Hello! We have received your query and are currently performing analysis in our system using our highly specialized AI agents. Please wait while we process your request..."
        supervisor_messages.append("Received user query, routing to triage agent")
        return {
            **state,
            "greeting_message": greeting_message,
            "supervisor_messages": supervisor_messages
        }
    else:
        # After triage - supervisor calls DeepSeek to decide next agent
        supervisor_messages.append("Triage complete. Analyzing routing decision...")
        
        user_query = state["user_query"]
        intent = state.get("intent", "unknown")
        sentiment = state.get("sentiment", "neutral")
        analysis = state.get("analysis", "")
        
        routing_prompt = f"""User Query: "{user_query}"
Intent: {intent}
Sentiment: {sentiment}
Analysis: {analysis}

Based on this information, which agent should handle this query?"""
        
        try:
            # Call DeepSeek to determine routing
            response = call_deepseek_chat(
                messages=[
                    {"role": "system", "content": SUPERVISOR_ROUTING_PROMPT},
                    {"role": "user", "content": routing_prompt}
                ],
                temperature=0.2
            )
            
            # Clean and parse the JSON response
            cleaned_response = response.strip()
            if cleaned_response.startswith("```"):
                cleaned_response = cleaned_response.split("```")[1]
                if cleaned_response.startswith("json"):
                    cleaned_response = cleaned_response[4:]
                cleaned_response = cleaned_response.strip()
            
            routing_result = json.loads(cleaned_response)
            next_agent = routing_result.get("next_agent", "general_information")
            reasoning = routing_result.get("reasoning", "Default routing")
            
            supervisor_messages.append(f"Routing to {next_agent} agent - {reasoning}")
            
            return {
                **state,
                "supervisor_messages": supervisor_messages,
                "next_agent": next_agent
            }
            
        except Exception as e:
            # Fallback to general_information on error
            supervisor_messages.append(f"Error in routing decision, defaulting to general_information - {str(e)}")
            return {
                **state,
                "supervisor_messages": supervisor_messages,
                "next_agent": "general_information"
            }


def triage_node(state: AgentState) -> AgentState:
    """
    Triage agent node - analyzes user query for intent and sentiment.
    Uses DeepSeek to classify the query.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with intent and sentiment
    """
    user_query = state["user_query"]
    triage_messages = state.get("triage_messages", [])

    user_prompt = f"Analyze this user query: \"{user_query}\""
    
    # Call DeepSeek API
    try:
        triage_messages.append("Analyzing query with DeepSeek...")
        
        response = call_deepseek_chat(
            messages=[
                {"role": "system", "content": TRIAGE_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2  # Lower temperature for more consistent classification
        )
        
        # Check for empty response
        if not response or not response.strip():
            raise ValueError("Empty response from DeepSeek API")
        
        # Clean and parse the JSON response
        # Remove markdown code blocks if present
        cleaned_response = response.strip()
        if cleaned_response.startswith("```"):
            # Extract content between code blocks
            cleaned_response = cleaned_response.split("```")[1]
            if cleaned_response.startswith("json"):
                cleaned_response = cleaned_response[4:]
            cleaned_response = cleaned_response.strip()
        
        # Parse the JSON response
        analysis_result = json.loads(cleaned_response)
        
        intent = analysis_result.get("intent", "unknown")
        sentiment = analysis_result.get("sentiment", "neutral")
        analysis = analysis_result.get("analysis", "Analysis completed")
        
        triage_messages.append(f"Classification complete - Intent: {intent}, Sentiment: {sentiment}")
        
        return {
            **state,
            "intent": intent,
            "sentiment": sentiment,
            "triage_messages": triage_messages,
            "analysis": analysis
        }
    
    except (json.JSONDecodeError, ValueError) as e:
        # Fallback if response is not valid JSON or empty
        triage_messages.append(f"Error parsing response, using fallback classification")
        # Log the problematic response for debugging
        response_preview = response[:200] if 'response' in locals() and response else "No response"
        print(f"DEBUG - Invalid response: {response_preview}")
        return {
            **state,
            "intent": "unknown",
            "sentiment": "neutral",
            "triage_messages": triage_messages,
            "analysis": f"Error parsing DeepSeek response: {str(e)}"
        }
    
    except Exception as e:
        # Handle any other errors
        triage_messages.append(f"Error during analysis - {str(e)}")
        return {
            **state,
            "intent": "error",
            "sentiment": "neutral",
            "triage_messages": triage_messages,
            "analysis": f"Error during analysis: {str(e)}"
        }


def general_information_node(state: AgentState) -> AgentState:
    """
    General Information Agent - Provides answers on policies, terms and conditions,
    and any other basic information about the platform to help users use it better.
    
    This agent uses a 3-step RAG approach:
    1. Category Selection: Select relevant categories from available data sources
    2. Document Selection: For each category, select relevant documents by doc_id
    3. Final Answer: Generate answer using the retrieved document content
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with final response
    """
    general_information_messages = state.get("general_information_messages", [])
    user_query = state["user_query"]
    
    general_information_messages.append("Processing query about platform information...")
    
    # Define data directory path
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    
    # Category to filename mapping
    category_files = {
        "Payment_Information": "Payment_Information.json",
        "Policies_&_Terms": "Policies_&_Terms.json",
        "product_specification_and_information": "product_specification_and_information.json"
    }
    
    try:
        # ===== STEP 1: Category Selection =====
        general_information_messages.append("Step 1: Selecting relevant categories...")
        
        category_prompt = f"User Query: {user_query}"
        
        category_response = call_deepseek_chat(
            messages=[
                {"role": "system", "content": CATEGORY_SELECTION_PROMPT},
                {"role": "user", "content": category_prompt}
            ],
            temperature=0.2
        )
        
        # Parse category selection response
        cleaned_response = category_response.strip()
        if cleaned_response.startswith("```"):
            cleaned_response = cleaned_response.split("```")[1]
            if cleaned_response.startswith("json"):
                cleaned_response = cleaned_response[4:]
            cleaned_response = cleaned_response.strip()
        
        category_result = json.loads(cleaned_response)
        selected_categories = category_result.get("selected_categories", [])
        
        general_information_messages.append(f"Selected categories: {', '.join(selected_categories)}")
        
        # ===== STEP 2: Document Selection for each category =====
        all_selected_doc_ids = []
        
        for category in selected_categories:
            if category not in category_files:
                general_information_messages.append(f"Warning: Unknown category '{category}', skipping...")
                continue
            
            general_information_messages.append(f"Step 2: Selecting documents from {category}...")
            
            # Load the category JSON file
            category_file_path = os.path.join(data_dir, category_files[category])
            
            with open(category_file_path, 'r', encoding='utf-8') as f:
                category_data = json.load(f)
            
            # Extract metadata for document selection
            documents_metadata = []
            for doc in category_data:
                metadata_info = {
                    "doc_id": doc.get("doc_id"),
                    "title": doc.get("title"),
                    "last_updated": doc.get("metadata", {}).get("last_updated", "N/A")
                }
                documents_metadata.append(metadata_info)
            
            # Ask LLM to select relevant doc_ids
            doc_selection_prompt = f"""User Query: {user_query}

Category: {category}

Available Documents:
{json.dumps(documents_metadata, indent=2)}

Select the relevant doc_ids that would help answer the user's query."""
            
            doc_response = call_deepseek_chat(
                messages=[
                    {"role": "system", "content": DOCUMENT_SELECTION_PROMPT},
                    {"role": "user", "content": doc_selection_prompt}
                ],
                temperature=0.2
            )
            
            # Parse document selection response
            cleaned_doc_response = doc_response.strip()
            if cleaned_doc_response.startswith("```"):
                cleaned_doc_response = cleaned_doc_response.split("```")[1]
                if cleaned_doc_response.startswith("json"):
                    cleaned_doc_response = cleaned_doc_response[4:]
                cleaned_doc_response = cleaned_doc_response.strip()
            
            doc_result = json.loads(cleaned_doc_response)
            selected_doc_ids = doc_result.get("selected_doc_ids", [])
            
            # Validate doc_ids exist in the data
            valid_doc_ids = [doc["doc_id"] for doc in category_data]
            validated_doc_ids = [doc_id for doc_id in selected_doc_ids if doc_id in valid_doc_ids]
            
            all_selected_doc_ids.extend(validated_doc_ids)
            general_information_messages.append(f"Selected {len(validated_doc_ids)} documents from {category}")
            if validated_doc_ids:
                general_information_messages.append(f"Doc IDs from {category}: {', '.join(validated_doc_ids)}")
        
        general_information_messages.append(f"Total documents selected: {len(all_selected_doc_ids)}")
        
        # ===== STEP 3: Extract content and generate final answer =====
        general_information_messages.append("Step 3: Generating final answer...")
        
        # Extract full content for selected doc_ids
        retrieved_documents = []
        
        for category in selected_categories:
            if category not in category_files:
                continue
            
            category_file_path = os.path.join(data_dir, category_files[category])
            
            with open(category_file_path, 'r', encoding='utf-8') as f:
                category_data = json.load(f)
            
            for doc in category_data:
                if doc.get("doc_id") in all_selected_doc_ids:
                    retrieved_documents.append({
                        "doc_id": doc.get("doc_id"),
                        "title": doc.get("title"),
                        "content": doc.get("content")
                    })
        
        # Create context from retrieved documents
        document_context = "\n\n".join([
            f"Document: {doc['title']}\nContent: {doc['content']}"
            for doc in retrieved_documents
        ])
        
        # Generate final answer
        final_answer_prompt = f"""User Query: {user_query}

Relevant Information:
{document_context}

Please provide a helpful answer to the user's query based on the above information."""
        
        final_response = call_deepseek_chat(
            messages=[
                {"role": "system", "content": FINAL_ANSWER_PROMPT},
                {"role": "user", "content": final_answer_prompt}
            ],
            temperature=0.3
        )
        
        general_information_messages.append("Response generated successfully")
        
        return {
            **state,
            "general_information_messages": general_information_messages,
            "final_response": final_response
        }
    
    except Exception as e:
        general_information_messages.append(f"Error processing query: {str(e)}")
        fallback_response = f"I apologize, but I encountered an error while processing your query. Please try again or contact support if the issue persists. Error: {str(e)}"
        
        return {
            **state,
            "general_information_messages": general_information_messages,
            "final_response": fallback_response
        }


def get_table_schemas() -> Dict[str, List[str]]:
    """
    Read CSV files and extract table schemas (column names).
    
    Returns:
        Dictionary mapping table names to their column lists
    """
    data_dir = Path(__file__).parent.parent / "data" / "personalised_agent"
    schemas = {}
    
    csv_files = {
        "user_info": "user_info.csv",
        "orders": "orders.csv",
        "order_items": "order_items.csv",
        "transactions": "transactions.csv",
        "cart": "cart.csv",
        "addresses": "addresses.csv",
        "returns": "returns.csv"
    }
    
    for table_name, csv_file in csv_files.items():
        csv_path = data_dir / csv_file
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader)
                schemas[table_name] = headers
        except Exception as e:
            print(f"Warning: Could not read schema for {table_name}: {e}")
    
    return schemas


def format_table_schemas(schemas: Dict[str, List[str]]) -> str:
    """
    Format table schemas into a readable string for the LLM.
    
    Args:
        schemas: Dictionary mapping table names to column lists
        
    Returns:
        Formatted string describing all tables and columns
    """
    formatted = []
    for table_name, columns in schemas.items():
        columns_str = ", ".join(columns)
        formatted.append(f"Table: {table_name}\nColumns: {columns_str}")
    
    return "\n\n".join(formatted)


async def generate_sql_from_subquery(subquery: str, table_schemas_str: str) -> Dict[str, Any]:
    """
    Generate SQL query from a subquery using DeepSeek (async).
    
    Args:
        subquery: Natural language subquery
        table_schemas_str: Formatted string of table schemas
        
    Returns:
        Dictionary with subquery, generated SQL, and any errors
    """
    try:
        sql_prompt = SQL_GENERATION_PROMPT.format(
            table_schemas=table_schemas_str,
            subquery=subquery
        )
        
        # Call DeepSeek synchronously but in an async context
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: call_deepseek_chat(
                messages=[
                    {"role": "system", "content": "You are a SQL query generation expert."},
                    {"role": "user", "content": sql_prompt}
                ],
                temperature=0.1
            )
        )
        
        # Parse the SQL response
        cleaned_response = response.strip()
        if cleaned_response.startswith("```"):
            cleaned_response = cleaned_response.split("```")[1]
            if cleaned_response.startswith("json"):
                cleaned_response = cleaned_response[4:]
            cleaned_response = cleaned_response.strip()
        
        sql_result = json.loads(cleaned_response)
        sql_query = sql_result.get("sql_query", "")
        
        return {
            "subquery": subquery,
            "sql_query": sql_query,
            "error": None
        }
    
    except Exception as e:
        return {
            "subquery": subquery,
            "sql_query": None,
            "error": str(e)
        }


async def execute_sql_query(sql_query: str, db_path: Path) -> Dict[str, Any]:
    """
    Execute SQL query on SQLite database (async).
    
    Args:
        sql_query: SQL query to execute
        db_path: Path to SQLite database
        
    Returns:
        Dictionary with query, results, and any errors
    """
    try:
        # Execute SQL in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        
        def execute():
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()
            cursor.execute(sql_query)
            rows = cursor.fetchall()
            
            # Convert rows to list of dictionaries
            results = [dict(row) for row in rows]
            conn.close()
            return results
        
        results = await loop.run_in_executor(None, execute)
        
        return {
            "sql_query": sql_query,
            "results": results,
            "error": None
        }
    
    except Exception as e:
        return {
            "sql_query": sql_query,
            "results": None,
            "error": str(e)
        }


def load_csv_data_to_db(data_dir: Path, db_path: Path):
    """
    Load CSV data into SQLite database tables if not already present.
    
    Args:
        data_dir: Directory containing CSV files
        db_path: Path to SQLite database
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    csv_files = {
        "user_info": "user_info.csv",
        "orders": "orders.csv",
        "order_items": "order_items.csv",
        "transactions": "transactions.csv",
        "cart": "cart.csv",
        "addresses": "addresses.csv",
        "returns": "returns.csv"
    }
    
    for table_name, csv_file in csv_files.items():
        # Check if table exists and has data
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if cursor.fetchone():
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            if count > 0:
                continue  # Table exists and has data
        
        # Read CSV and create table
        csv_path = data_dir / csv_file
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                
                # Drop table if exists
                cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                
                # Create table with all columns as TEXT for simplicity
                columns = ", ".join([f"{col} TEXT" for col in headers])
                cursor.execute(f"CREATE TABLE {table_name} ({columns})")
                
                # Insert data
                placeholders = ", ".join(["?" for _ in headers])
                for row in reader:
                    values = [row[col] for col in headers]
                    cursor.execute(f"INSERT INTO {table_name} VALUES ({placeholders})", values)
                
                print(f"Loaded {table_name} from {csv_file}")
        
        except Exception as e:
            print(f"Error loading {table_name}: {e}")
    
    conn.commit()
    conn.close()


def personalised_rag_node(state: AgentState) -> AgentState:
    """
    Personalised RAG Agent - Answers questions on personal information from the SQLite database.
    
    This agent implements a multi-step RAG approach:
    1. Get table schemas from CSV files
    2. Generate subqueries using LLM (max 5)
    3. Generate SQL queries from subqueries in parallel using asyncio
    4. Execute SQL queries in parallel
    5. Generate final answer from aggregated results
    
    This agent handles queries about:
    - Order status and history
    - Transaction details
    - Account information
    - User-specific data
    - Purchase history
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with final response
    """
    personalised_rag_messages = state.get("personalised_rag_messages", [])
    user_query = state["user_query"]
    
    personalised_rag_messages.append("Processing query about personal user data...")
    
    try:
        # Define paths
        data_dir = Path(__file__).parent.parent / "data" / "personalised_agent"
        db_path = Path(__file__).parent.parent / "hackfest.db"
        
        # Load CSV data into database if needed
        personalised_rag_messages.append("Setting up database from CSV files...")
        load_csv_data_to_db(data_dir, db_path)
        
        # ===== STEP 1: Get table schemas =====
        personalised_rag_messages.append("Step 1: Loading table schemas...")
        schemas = get_table_schemas()
        table_schemas_str = format_table_schemas(schemas)
        personalised_rag_messages.append(f"Loaded {len(schemas)} tables")
        
        # ===== STEP 2: Generate subqueries =====
        personalised_rag_messages.append("Step 2: Generating subqueries...")
        
        subquery_prompt = SUBQUERY_GENERATION_PROMPT.format(
            table_schemas=table_schemas_str
        )
        
        subquery_response = call_deepseek_chat(
            messages=[
                {"role": "system", "content": "You are an intelligent query decomposition agent."},
                {"role": "user", "content": f"User Query: {user_query}\n\n{subquery_prompt}"}
            ],
            temperature=0.2
        )
        
        # Parse subquery response
        cleaned_response = subquery_response.strip()
        if cleaned_response.startswith("```"):
            cleaned_response = cleaned_response.split("```")[1]
            if cleaned_response.startswith("json"):
                cleaned_response = cleaned_response[4:]
            cleaned_response = cleaned_response.strip()
        
        subquery_result = json.loads(cleaned_response)
        subqueries = subquery_result.get("subqueries", [])[:5]  # Max 5 subqueries
        
        personalised_rag_messages.append(f"Generated {len(subqueries)} subqueries")
        
        if not subqueries:
            raise ValueError("No subqueries generated")
        
        # ===== STEP 3: Generate SQL queries in parallel =====
        personalised_rag_messages.append("Step 3: Generating SQL queries in parallel...")
        
        async def generate_all_sql():
            tasks = [
                generate_sql_from_subquery(subquery, table_schemas_str)
                for subquery in subqueries
            ]
            return await asyncio.gather(*tasks)
        
        # Run async tasks
        sql_results = asyncio.run(generate_all_sql())
        
        # Filter out failed SQL generations
        valid_sql_queries = [
            result for result in sql_results
            if result["sql_query"] and not result["error"]
        ]
        
        personalised_rag_messages.append(f"Generated {len(valid_sql_queries)} valid SQL queries")
        
        if not valid_sql_queries:
            raise ValueError("No valid SQL queries generated")
        
        # ===== STEP 4: Execute SQL queries in parallel =====
        personalised_rag_messages.append("Step 4: Executing SQL queries in parallel...")
        
        async def execute_all_queries():
            tasks = [
                execute_sql_query(result["sql_query"], db_path)
                for result in valid_sql_queries
            ]
            return await asyncio.gather(*tasks)
        
        # Run async tasks
        query_results = asyncio.run(execute_all_queries())
        
        # Aggregate successful results
        all_results = []
        for idx, result in enumerate(query_results):
            if result["results"] is not None and not result["error"]:
                all_results.append({
                    "subquery": valid_sql_queries[idx]["subquery"],
                    "sql_query": result["sql_query"],
                    "results": result["results"]
                })
                personalised_rag_messages.append(
                    f"Query {idx+1} returned {len(result['results'])} rows"
                )
            else:
                personalised_rag_messages.append(
                    f"Query {idx+1} failed: {result['error']}"
                )
        
        # ===== STEP 5: Generate final answer =====
        personalised_rag_messages.append("Step 5: Generating final answer...")
        
        # Format results for LLM
        results_context = "\n\n".join([
            f"Subquery: {r['subquery']}\n"
            f"SQL: {r['sql_query']}\n"
            f"Results ({len(r['results'])} rows):\n{json.dumps(r['results'], indent=2)}"
            for r in all_results
        ])
        
        final_answer_prompt = f"""User Query: {user_query}

Database Query Results:
{results_context}

Please provide a helpful, personalized answer based on the above data."""
        
        final_response = call_deepseek_chat(
            messages=[
                {"role": "system", "content": PERSONALIZED_FINAL_ANSWER_PROMPT},
                {"role": "user", "content": final_answer_prompt}
            ],
            temperature=0.3
        )
        
        personalised_rag_messages.append("Response generated successfully")
        
        return {
            **state,
            "personalised_rag_messages": personalised_rag_messages,
            "final_response": final_response
        }
    
    except Exception as e:
        personalised_rag_messages.append(f"Error processing query: {str(e)}")
        fallback_response = f"I apologize, but I encountered an error while processing your personal data query. Please try rephrasing your question or contact support if the issue persists. Error: {str(e)}"
        
        return {
            **state,
            "personalised_rag_messages": personalised_rag_messages,
            "final_response": fallback_response
        }


def escalation_node(state: AgentState) -> AgentState:
    """
    Escalation Agent - Passes complex problems to human support by creating a ticket.
    
    This agent handles:
    - Complex technical issues
    - Complaints requiring human intervention
    - Problems that cannot be resolved automatically
    - Requests for human support
    
    The agent creates a support ticket with full context about the user's problem.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with final response
    """
    escalation_messages = state.get("escalation_messages", [])
    user_query = state["user_query"]
    intent = state.get("intent", "unknown")
    sentiment = state.get("sentiment", "neutral")
    analysis = state.get("analysis", "")
    
    escalation_messages.append("Creating support ticket for human agent...")
    
    # TODO: Implement functionality to:
    # 1. Generate unique ticket ID
    # 2. Collect all relevant user information
    # 3. Store ticket in database
    # 4. Send notification to support team
    # 5. Provide ticket details to user
    
    # Placeholder response for now
    ticket_id = "TICKET-PLACEHOLDER-001"
    
    final_response = f"""[Escalation Agent Response]

Thank you for reaching out. Your issue has been escalated to our human support team.

Ticket Details:
- Ticket ID: {ticket_id}
- Status: Open
- Priority: Medium
- Query: {user_query}
- Intent: {intent}
- Sentiment: {sentiment}

A support agent will review your case and contact you shortly. The actual implementation will include:
- Real ticket generation with unique ID
- Database storage of ticket information
- Email/notification system
- Full user context and history
- Integration with support ticket system

This is a template response that will be customized later.
"""
    
    escalation_messages.append(f"Support ticket {ticket_id} created successfully")
    
    return {
        **state,
        "escalation_messages": escalation_messages,
        "final_response": final_response
    }

