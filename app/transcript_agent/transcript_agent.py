"""
Transcript Agent for Sleeping Helper News Reader

This agent uses LangGraph to generate soothing news transcripts for sleep assistance.
It maintains context across multiple news items and generates paragraphs suitable for
bedtime reading.
"""

import json
from typing import TypedDict, List, Dict, Any, Annotated
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
import operator



# Define the state structure
class TranscriptState(TypedDict):
    """State for the transcript generation agent"""
    # Current input
    current_input: Dict[str, Any]  # {summary: str, comments: List[str]}
    
    # Generated paragraphs for current news
    current_paragraphs: List[str]
    
    # Context: all previously generated paragraphs
    previous_paragraphs: Annotated[List[str], operator.add]
    
    # Flag to check if this is the first news item
    is_first_news: bool
    
    # Flag to add sleep guidance
    add_sleep_guidance: bool
    
    # Final output
    output: Dict[str, Any]


def generate_transcript_paragraphs(state: TranscriptState) -> TranscriptState:
    """
    Node to generate transcript paragraphs based on news summary and comments.
    Uses LLM to create engaging, sleep-friendly content.
    """
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", temperature=0.7)
    
    news_summary = state["current_input"]["summary"]
    comments = state["current_input"].get("comments", [])
    previous_paragraphs = state.get("previous_paragraphs", [])
    is_first_news = state.get("is_first_news", False)
    add_sleep_guidance = state.get("add_sleep_guidance", False)
    
    # Build context from previous paragraphs
    context_info = ""
    if previous_paragraphs:
        # Only show last few paragraphs for context
        recent_context = previous_paragraphs[-3:] if len(previous_paragraphs) > 3 else previous_paragraphs
        context_info = f"\n\nPrevious paragraphs for context:\n" + "\n".join(recent_context)
    
    # Build the prompt
    prompt_parts = []
    
    if is_first_news:
        prompt_parts.append(
            "You are creating the opening of a sleep-inducing news podcast. "
            "Start with a warm greeting like 'Good evening, welcome to Sleepy News Channel, "
            "and I'm your news anchor Bob.' Keep it calm and soothing."
        )
    else:
        prompt_parts.append(
            "You are continuing a sleep-inducing news podcast. "
            "Add a smooth transition from the previous topic. "
            "Use transitional phrases to connect topics naturally."
        )
    
    prompt_parts.append(f"""
Generate a soothing transcript for bedtime news reading with the following requirements:

1. Create 2-3 paragraphs about this news:
   {news_summary}

2. If there are short and interesting comments, create 1 paragraph to read one or two original comments in a funny way.
   {json.dumps(comments, indent=2)}

3. Each paragraph MUST NOT exceed 50 words.
4. Use a calm, gentle tone suitable for helping someone fall asleep.
5. Keep the content informative but not alarming or exciting.
""")
    
    if add_sleep_guidance:
        prompt_parts.append("""
6. Add an intermediate paragraph with gentle sleep guidance (breathing, relaxation, etc.). Sth like "while we are discussiing the news, don't forget to breathe slowly".
   Keep it under 50 words and very soothing.
""")
    
    if context_info:
        prompt_parts.append(f"""
Maintain consistency with the previous content:{context_info}
""")
    
    prompt_parts.append("""
Remember that we are constantly generating new paragraphs, so don't say things like that's it for today's news or good night etc. Just keep talking.
Output ONLY a JSON array of paragraph strings, nothing else. Format:
["paragraph 1", "paragraph 2", "paragraph 3", ...]
""")
    
    full_prompt = "\n".join(prompt_parts)
    
    # Generate the paragraphs
    response = llm.invoke([HumanMessage(content=full_prompt)])
    
    # Parse the response
    try:
        # Extract JSON from response
        content = response.content.strip()
        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()
        
        paragraphs = json.loads(content)
        
        if not isinstance(paragraphs, list):
            paragraphs = [content]
    except json.JSONDecodeError:
        # Fallback: split by newlines if JSON parsing fails
        paragraphs = [p.strip() for p in response.content.split("\n\n") if p.strip()]
    
    return {
        **state,
        "current_paragraphs": paragraphs
    }


def prepare_output(state: TranscriptState) -> TranscriptState:
    """
    Node to prepare the final output in JSON format.
    """
    output = {
        "paragraphs": state["current_paragraphs"]
    }
    
    return {
        **state,
        "output": output,
        "previous_paragraphs": state["current_paragraphs"]  # Add to context
    }


class TranscriptAgent:
    """
    LangGraph-based agent for generating sleep-friendly news transcripts.
    """
    
    def __init__(self):
        """Initialize the transcript agent with LangGraph workflow."""
        self.graph = self._build_graph()
        self.context_paragraphs = []  # Maintain context across invocations
        self.news_count = 0  # Track how many news items processed
        
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(TranscriptState)
        
        # Add nodes
        workflow.add_node("generate_paragraphs", generate_transcript_paragraphs)
        workflow.add_node("prepare_output", prepare_output)
        
        # Add edges
        workflow.set_entry_point("generate_paragraphs")
        workflow.add_edge("generate_paragraphs", "prepare_output")
        workflow.add_edge("prepare_output", END)
        
        return workflow.compile()
    
    def process_news(self, news_input: Dict[str, Any], add_sleep_guidance: bool = False) -> Dict[str, Any]:
        """
        Process a news item and generate transcript paragraphs.
        
        Args:
            news_input: Dictionary with 'summary' and 'comments' keys
            add_sleep_guidance: Whether to add sleep guidance paragraph at the end
            
        Returns:
            Dictionary with 'paragraphs' key
        """
        self.news_count += 1
        is_first = self.news_count == 1
        
        # Prepare initial state
        initial_state = {
            "current_input": news_input,
            "current_paragraphs": [],
            "previous_paragraphs": self.context_paragraphs.copy(),
            "is_first_news": is_first,
            "add_sleep_guidance": add_sleep_guidance,
            "output": {}
        }
        
        # Run the graph
        result = self.graph.invoke(initial_state)
        
        # Update context with new paragraphs (but not the input)
        self.context_paragraphs.extend(result["current_paragraphs"])
        
        return result["output"]
    
    def reset_context(self):
        """Reset the agent's context for a new session."""
        self.context_paragraphs = []
        self.news_count = 0


# Example usage
if __name__ == "__main__":
    # Initialize the agent
    agent = TranscriptAgent()
    
    # Example news items (with pre-fetched summaries)
    news_items = [
        {
            "summary": "A major breakthrough in renewable energy technology has been announced, promising to revolutionize solar power efficiency by 40%.",
            "comments": [
                "This is amazing progress!",
                "Can't wait to see this in action",
                "Wondering about the implications for privacy"
            ]
        },
        {
            "summary": "Two journalists have been awarded the 2025 Sakharov Prize for their courageous reporting on human rights issues.",
            "comments": [
                "We need more action on this",
                "Interesting data points",
                "Hope for a better future"
            ]
        }
    ]
    
    print("Starting Sleepy News Channel transcript generation...\n")
    
    # Process first news (with greeting)
    result1 = agent.process_news(news_items[0], add_sleep_guidance=False)
    print("News 1 Output:")
    print(json.dumps(result1, indent=2))
    print("\n" + "="*60 + "\n")
    
    # Process second news (with transition and sleep guidance)
    result2 = agent.process_news(news_items[1], add_sleep_guidance=True)
    print("News 2 Output:")
    print(json.dumps(result2, indent=2))
    print("\n" + "="*60 + "\n")
    
    # Show all generated paragraphs in order
    print("Complete Transcript:")
    for i, para in enumerate(agent.context_paragraphs, 1):
        print(f"{i}. {para}")


