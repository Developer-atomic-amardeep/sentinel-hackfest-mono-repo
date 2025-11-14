from langgraph.graph import StateGraph, START, END
from agents.states import AgentState
from agents.nodes import (
    supervisor_node, 
    triage_node,
    general_information_node,
    personalised_rag_node,
    escalation_node
)


def route_after_supervisor(state: AgentState) -> str:
    """
    Router function to determine which agent to call after supervisor.
    
    Args:
        state: Current agent state
        
    Returns:
        Name of the next node to execute
    """
    # If no intent yet, go to triage
    if not state.get("intent"):
        return "triage"
    
    # After triage, supervisor has called DeepSeek and set next_agent
    # Route based on supervisor's decision
    next_agent = state.get("next_agent", "general_information")
    
    if next_agent == "personalised_rag":
        return "personalised_rag"
    elif next_agent == "escalation":
        return "escalation"
    else:
        return "general_information"


def create_workflow():
    """
    Creates and compiles the LangGraph workflow for the multi-agent system.
    
    Workflow:
    1. START → supervisor (receives query and initiates orchestration)
    2. supervisor → triage (forwards to triage for analysis)
    3. triage → supervisor (returns with intent and sentiment analysis)
    4. supervisor → calls DeepSeek to determine routing decision
    5. supervisor → [general_information | personalised_rag | escalation] (routes to appropriate agent)
    6. [agent] → END (agent returns final response)
    
    Returns:
        Compiled LangGraph workflow
    """
    # Initialize the StateGraph with our AgentState schema
    workflow = StateGraph(AgentState)
    
    # Add all nodes to the graph
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("triage", triage_node)
    workflow.add_node("general_information", general_information_node)
    workflow.add_node("personalised_rag", personalised_rag_node)
    workflow.add_node("escalation", escalation_node)
    
    # Define the workflow edges
    # START → supervisor (initial entry point)
    workflow.add_edge(START, "supervisor")
    
    # supervisor uses conditional routing
    workflow.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "triage": "triage",
            "general_information": "general_information",
            "personalised_rag": "personalised_rag",
            "escalation": "escalation"
        }
    )
    
    # triage → supervisor (return to supervisor with routing decision)
    workflow.add_edge("triage", "supervisor")
    
    # All specialized agents end the workflow
    workflow.add_edge("general_information", END)
    workflow.add_edge("personalised_rag", END)
    workflow.add_edge("escalation", END)
    
    # Compile the graph
    compiled_workflow = workflow.compile()
    
    return compiled_workflow


# Create and export the compiled workflow
workflow = create_workflow()
