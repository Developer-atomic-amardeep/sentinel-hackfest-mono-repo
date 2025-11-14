"""
Pydantic Models for API Request/Response

This module contains Pydantic models used for FastAPI endpoints.
For LangGraph state definitions, see states.py
"""

from pydantic import BaseModel, Field


class AnalyzeQueryRequest(BaseModel):
    """Request model for the analyze query endpoint"""
    user_query: str = Field(..., description="The user query to analyze", min_length=1)
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_query": "I'm having trouble logging into my account and it's very frustrating!"
            }
        }


class AnalyzeQueryResponse(BaseModel):
    """Response model for the analyze query endpoint"""
    intent: str = Field(..., description="The classified intent of the user query")
    sentiment: str = Field(..., description="The sentiment classification (positive/negative/neutral)")
    analysis: str = Field(..., description="Detailed analysis from the triage agent")
    next_agent: str = Field(..., description="The agent that handled the query (general_information/personalised_rag/escalation)")
    final_response: str = Field(..., description="The final response to the user from the specialized agent")
    user_query: str = Field(..., description="The original user query")
    
    class Config:
        json_schema_extra = {
            "example": {
                "intent": "technical_support",
                "sentiment": "negative",
                "analysis": "User is experiencing login issues and expressing frustration",
                "next_agent": "escalation",
                "final_response": "Your issue has been escalated to our support team...",
                "user_query": "I'm having trouble logging into my account and it's very frustrating!"
            }
        }

