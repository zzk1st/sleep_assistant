"""
Transcript Agent for Sleeping Helper News Reader

This agent uses LangGraph to generate soothing news transcripts for sleep assistance.
It maintains context across multiple news items and generates paragraphs suitable for
bedtime reading.
"""

import os
import json
from typing import TypedDict, List, Dict, Any, Annotated
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
import operator
import tempfile
import httpx
import markitdown
import requests



# Define the state structure
class TranscriptState(TypedDict):
    """State for the transcript generation agent"""
    # Current input
    current_input: Dict[str, Any]  # {url: str, comments: List[str]}
    
    # News summary from webpage_to_summary tool
    news_summary: str
    
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


def _fetch_text_local(
    url: str,
) -> str:
    """Convert a document file to text using markitdown.

    Args:
        url: URL of the PDF file

    Returns:
        str: Extracted text from the PDF
    """

    try:
        # Create a temporary file to store the downloaded document
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            # Download the document file
            timeout = httpx.Timeout(connect=20.0, read=10.0, write=10.0, pool=None)
            with httpx.Client(timeout=timeout) as client:
                response = client.get(url)
                if response.status_code != 200:
                    print(f"Failed to download document from {url}")
                    raise ValueError(f"Failed to download document from {url}, status code: {response.status_code}")

                # Save the downloaded content to the temporary file
                temp_file.write(response.content)
                temp_file.flush()

                # Convert document to text using markitdown
                result = markitdown.MarkItDown().convert(temp_file.name)
                if result and result.text_content:
                    print(f"Successfully extracted text from {url}")
                    return str(result.text_content)
                else:
                    print(f"No text content found in {url}")
                    raise ValueError(f"No text content found in {url}")
    except Exception as e:
        print(f"Error converting document to text: {str(e)}")
        raise e
    finally:
        # Clean up the temporary file
        try:
            os.unlink(temp_file.name)
        except Exception as e:
            print(f"Failed to delete temporary file {temp_file.name}: {str(e)}")


def get_news_from_gemini(page_text: str) -> str:
    """
    Uses the Gemini API to extract the main news article from cleaned webpage text.

    Args:
        page_text: The cleaned text extracted from the webpage.

    Returns:
        The extracted news article text, or an error message.
    """
    if not page_text:
        return "Error: No text was provided to analyze."

    # Securely get the API key from an environment variable
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return (
            "Error: GEMINI_API_KEY environment variable not set.\n"
            "Please set the environment variable with your API key."
        )

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={api_key}"

    system_prompt = (
        "You are an expert news article extractor. Your task is to analyze the "
        "provided text, which has been scraped from a news webpage, and return "
        "the summary of the news article. You must remove all advertisements, "
        "navigation links, related articles sections, comments, author bios, "
        "and any other non-essential text. The output should be the clean, "
        "readable news article, including its title and body. The output should be no more than 200 words."
    )

    payload = {
        "contents": [{"parts": [{"text": page_text}]}],
        "systemInstruction": {
            "parts": [{"text": system_prompt}]
        },
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2048,
        }
    }

    try:
        response = requests.post(api_url, json=payload, headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        result = response.json()
        
        candidate = result.get('candidates', [{}])[0]
        if 'content' in candidate and 'parts' in candidate['content']:
            return candidate['content']['parts'][0].get('text', "Error: Could not extract text from API response.")
        else:
            return f"Error: The API response did not contain the expected content. Response: {result}"
            
    except requests.exceptions.RequestException as e:
        return f"Error: API request failed. Reason: {e}"
    except (KeyError, IndexError) as e:
        return f"Error: Failed to parse API response. Reason: {e}. Response: {result}"


def webpage_to_summary(url: str) -> str:
    """
    Tool to extract and summarize webpage content.
    
    This is a placeholder function. Fill in the implementation to:
    1. Fetch the webpage content from the URL
    2. Extract the main article text
    3. Generate a concise summary
    
    Args:
        url: The URL of the news webpage
        
    Returns:
        A summary of the webpage content
    """
    page_text = _fetch_text_local(url)
    return get_news_from_gemini(page_text)


def fetch_news_summary(state: TranscriptState) -> TranscriptState:
    """
    Node to fetch and summarize the news from the provided URL.
    """
    url = state["current_input"]["url"]
    summary = webpage_to_summary(url)
    print(f"Summary: {summary}")
    
    return {
        **state,
        "news_summary": summary
    }


def generate_transcript_paragraphs(state: TranscriptState) -> TranscriptState:
    """
    Node to generate transcript paragraphs based on news summary and comments.
    Uses LLM to create engaging, sleep-friendly content.
    """
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", temperature=0.7)
    
    news_summary = state["news_summary"]
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
            "and I'm your news anchor [name].' Keep it calm and soothing."
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

2. Create 1 paragraph discussing these user comments:
   {json.dumps(comments, indent=2)}

3. Each paragraph MUST NOT exceed 50 words.
4. Use a calm, gentle tone suitable for helping someone fall asleep.
5. Keep the content informative but not alarming or exciting.
""")
    
    if add_sleep_guidance:
        prompt_parts.append("""
6. Add a final paragraph with gentle sleep guidance (breathing, relaxation, etc.).
   Keep it under 50 words and very soothing.
""")
    
    if context_info:
        prompt_parts.append(f"""
Maintain consistency with the previous content:{context_info}
""")
    
    prompt_parts.append("""
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
        "url": state["current_input"]["url"],
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
        workflow.add_node("fetch_summary", fetch_news_summary)
        workflow.add_node("generate_paragraphs", generate_transcript_paragraphs)
        workflow.add_node("prepare_output", prepare_output)
        
        # Add edges
        workflow.set_entry_point("fetch_summary")
        workflow.add_edge("fetch_summary", "generate_paragraphs")
        workflow.add_edge("generate_paragraphs", "prepare_output")
        workflow.add_edge("prepare_output", END)
        
        return workflow.compile()
    
    def process_news(self, news_input: Dict[str, Any], add_sleep_guidance: bool = False) -> Dict[str, Any]:
        """
        Process a news item and generate transcript paragraphs.
        
        Args:
            news_input: Dictionary with 'url' and 'comments' keys
            add_sleep_guidance: Whether to add sleep guidance paragraph at the end
            
        Returns:
            Dictionary with 'url' and 'paragraphs' keys
        """
        self.news_count += 1
        is_first = self.news_count == 1
        
        # Prepare initial state
        initial_state = {
            "current_input": news_input,
            "news_summary": "",
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
    
    # Example news items
    news_items = [
        {
            "url": "https://www.bbc.com/news/articles/czjpe0193geo",
            "comments": [
                "This is amazing progress!",
                "Can't wait to see this in action",
                "Wondering about the implications for privacy"
            ]
        },
        {
            "url": "https://www.europarl.europa.eu/news/en/press-room/20251016IPR30949/andrzej-poczobut-and-mzia-amaglobeli-laureates-of-the-2025-sakharov-prize",
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


