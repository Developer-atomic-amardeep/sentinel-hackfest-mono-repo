"""
LangGraph State Definitions

This module contains all state definitions used in the LangGraph workflows.
States are used to track data as it flows through the agent pipeline.
"""

from typing import TypedDict, Optional, List, Annotated
from operator import add


class AgentState(TypedDict):
    """
    Main state object for the supervisor-triage LangGraph workflow.
    
    This state tracks the user query and analysis results as they flow
    through the agent pipeline from supervisor to triage and back.
    
    Attributes:
        user_query: The original user query to analyze
        intent: The classified intent/purpose of the query (e.g., technical_support, complaint)
        sentiment: The sentiment classification (positive, negative, or neutral)
        supervisor_messages: Messages from supervisor agent
        triage_messages: Messages from triage agent
        general_information_messages: Messages from general information agent
        personalised_rag_messages: Messages from personalised RAG agent
        escalation_messages: Messages from escalation agent
        analysis: Detailed analysis text from the triage agent
        next_agent: The agent to route to (general_information, personalised_rag, escalation)
        final_response: The final response to return to the user
        greeting_message: Initial greeting message shown to the user
    """
    user_query: str
    intent: Optional[str]
    sentiment: Optional[str]
    supervisor_messages: Annotated[List[str], add]
    triage_messages: Annotated[List[str], add]
    general_information_messages: Annotated[List[str], add]
    personalised_rag_messages: Annotated[List[str], add]
    escalation_messages: Annotated[List[str], add]
    analysis: Optional[str]
    next_agent: Optional[str]
    final_response: Optional[str]
    greeting_message: Optional[str]


class StreamingState(TypedDict, total=False):
    """
    Extended state for streaming workflows.
    
    Adds additional fields useful for tracking streaming progress
    and providing real-time updates to clients.
    
    Attributes:
        All fields from AgentState, plus:
        current_node: Name of the currently executing node
        progress: Progress indicator (e.g., "1/3", "2/3")
        timestamp: ISO timestamp of last update
    """
    user_query: str
    intent: Optional[str]
    sentiment: Optional[str]
    messages: Annotated[List[str], add]
    analysis: Optional[str]
    current_node: Optional[str]
    progress: Optional[str]
    timestamp: Optional[str]

