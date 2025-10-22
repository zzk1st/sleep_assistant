# Transcript Agent for Sleeping Helper

A LangGraph-based agent that generates soothing news transcripts for bedtime reading. The agent maintains context across multiple news items and creates sleep-friendly content.

## Features

- **LangGraph Workflow**: Structured agent with clear state management
- **Context Maintenance**: Keeps track of previously generated paragraphs for consistency
- **Smooth Transitions**: Automatically adds transitional sentences between news items
- **Sleep Guidance**: Option to include relaxation/breathing guidance
- **Word Limit Control**: Ensures each paragraph stays under 50 words
- **Opening Greeting**: First news item includes a welcoming introduction

## Architecture

The agent uses a LangGraph state graph with the following nodes:

1. **fetch_summary**: Calls `webpage_to_summary` tool to get news summary
2. **generate_paragraphs**: Uses LLM to create transcript paragraphs
3. **prepare_output**: Formats output and updates context

### State Structure

- `current_input`: The input JSON with URL and comments
- `news_summary`: Summary from webpage_to_summary tool
- `current_paragraphs`: Generated paragraphs for current news
- `previous_paragraphs`: Context from all previous news items
- `is_first_news`: Flag for adding opening greeting
- `add_sleep_guidance`: Flag for including sleep guidance
- `output`: Final JSON output

## Installation

```bash
pip install -r requirements.txt
```

You'll need to set your Google API key:

```bash
export GOOGLE_API_KEY='your-google-api-key-here'
```

## Implementation Steps

### 1. Implement `webpage_to_summary` Function

The `webpage_to_summary` function is currently a placeholder. You need to implement it to:

- Fetch webpage content from the URL
- Extract the main article text
- Generate a concise summary

Example implementation options:

```python
# Option 1: Using requests + BeautifulSoup + LLM
import requests
from bs4 import BeautifulSoup
from langchain_google_genai import ChatGoogleGenerativeAI

def webpage_to_summary(url: str) -> str:
    # Fetch webpage
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Extract article text (adjust selectors for your target sites)
    article = soup.find('article') or soup.find('main')
    text = article.get_text() if article else soup.get_text()
    
    # Summarize with LLM
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp")
    summary = llm.invoke(f"Summarize this news article concisely:\n\n{text[:5000]}")
    
    return summary.content

# Option 2: Using Firecrawl or similar service
# Option 3: Using newspaper3k library
```

### 2. Usage

```python
from transcript_agent import TranscriptAgent

# Initialize the agent
agent = TranscriptAgent()

# Process news items
news_input = {
    "url": "https://example.com/news/article",
    "comments": [
        "Great article!",
        "Very informative",
        "Thanks for sharing"
    ]
}

# First news (includes greeting)
result = agent.process_news(news_input, add_sleep_guidance=False)
print(result)
# Output: {"url": "...", "paragraphs": ["Good evening...", "...", "..."]}

# Next news (includes transition)
result2 = agent.process_news(another_news, add_sleep_guidance=True)

# Reset context when starting a new session
agent.reset_context()
```

## Configuration

### When to Add Sleep Guidance

You can control when to add sleep guidance paragraphs by setting the `add_sleep_guidance` parameter. Recommended strategy:

```python
# Add sleep guidance every 3-4 news items
for i, news in enumerate(news_items):
    add_guidance = (i + 1) % 3 == 0  # Every 3rd news
    result = agent.process_news(news, add_sleep_guidance=add_guidance)
```

### Adjusting LLM Settings

Modify the LLM configuration in `generate_transcript_paragraphs`:

```python
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-exp",  # or "gemini-1.5-pro" for better quality
    temperature=0.7,                # 0.7 for creative, 0.3 for consistent
)
```

## Example Output

```json
{
  "url": "https://example.com/news/tech-breakthrough",
  "paragraphs": [
    "Good evening, welcome to Sleepy News Channel, and I'm your news anchor Luna. Tonight we bring you stories to gently inform as you drift off to sleep.",
    "Researchers have unveiled a new breakthrough in renewable energy technology. The innovation promises to make solar panels more efficient and affordable for households worldwide.",
    "This development comes after years of dedicated research. Scientists believe this could significantly reduce carbon emissions while making clean energy accessible to millions of families.",
    "Many viewers shared their thoughts on this news. Some expressed excitement about the environmental benefits, while others wondered about implementation timelines. The general sentiment reflects hope for a sustainable future.",
    "As you absorb this hopeful news, take a deep breath in through your nose. Hold for a moment, then slowly exhale. Feel yourself relaxing deeper into comfort and rest."
  ]
}
```

## Testing

Run the example:

```bash
python transcript_agent.py
```

This will process two example news items and display the generated transcripts.

## Notes

- The agent maintains context only for generated paragraphs, not input JSON objects
- First news item automatically includes an opening greeting
- Transitional sentences are added between news items
- Each paragraph is limited to 50 words maximum
- The tone is kept calm and soothing throughout
- Context is preserved across multiple `process_news()` calls
- Call `reset_context()` to start a new session

## Future Enhancements

- Add support for custom anchor names
- Implement different speaking styles
- Add audio generation from transcript
- Support for multiple languages
- Category-based routing (tech, sports, politics, etc.)
- Automatic detection of when to add sleep guidance


