"""
Agents Module

LangGraph workflow implementation for supervisor-triage agent system.

This module provides:
- State definitions for workflow tracking
- Pydantic models for API integration
- Agent nodes (supervisor, triage)
- Compiled workflow graph
- Utility functions for DeepSeek API

Usage:
    from agents import workflow, AgentState, AnalyzeQueryRequest
    
    initial_state = {
        "user_query": "User query here",
        "intent": None,
        "sentiment": None,
        "messages": [],
        "analysis": None
    }
    
    result = workflow.invoke(initial_state)
"""

# State definitions
from agents.states import AgentState, StreamingState

# API models
from agents.models import AnalyzeQueryRequest, AnalyzeQueryResponse

# Agent nodes
from agents.nodes import supervisor_node, triage_node

# Compiled workflow
from agents.graph import workflow, create_workflow

# Utilities
from agents.utils import get_deepseek_client, call_deepseek_chat

# Prompts
from agents.prompts import TRIAGE_PROMPT


__all__ = [
    # States
    "AgentState",
    "StreamingState",
    
    # Models
    "AnalyzeQueryRequest",
    "AnalyzeQueryResponse",
    
    # Nodes
    "supervisor_node",
    "triage_node",
    
    # Workflow
    "workflow",
    "create_workflow",
    
    # Utils
    "get_deepseek_client",
    "call_deepseek_chat",
    
    # Prompts
    "TRIAGE_PROMPT",
]

