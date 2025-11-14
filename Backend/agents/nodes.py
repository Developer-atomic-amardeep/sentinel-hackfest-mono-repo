import json
import os
from agents.states import AgentState
from agents.utils import call_deepseek_chat
from agents.prompts import (
    TRIAGE_PROMPT, 
    SUPERVISOR_ROUTING_PROMPT,
    CATEGORY_SELECTION_PROMPT,
    DOCUMENT_SELECTION_PROMPT,
    FINAL_ANSWER_PROMPT
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
        supervisor_messages.append("Received user query, routing to triage agent")
        return {
            **state,
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


def personalised_rag_node(state: AgentState) -> AgentState:
    """
    Personalised RAG Agent - Answers questions on personal information from the SQLite database.
    
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
    
    # TODO: Implement functionality to:
    # 1. Extract user identifier from query or session
    # 2. Query SQLite database for user-specific information
    # 3. Retrieve relevant order, transaction, and account data
    # 4. Generate personalized response based on user's data
    
    # Placeholder response for now
    final_response = f"[Personalised RAG Agent Response]\n\nThank you for your query: '{user_query}'\n\nThis agent will provide personalized information from your account. The actual implementation will include:\n- Database queries for order status\n- Transaction history retrieval\n- Account details lookup\n- Personalized recommendations\n\nThis is a template response that will be customized later."
    
    personalised_rag_messages.append("Response generated successfully")
    
    return {
        **state,
        "personalised_rag_messages": personalised_rag_messages,
        "final_response": final_response
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

