"""
Utility functions for the sleep assistant application.
"""

import os
import tempfile
import httpx
import markitdown
import requests


def _fetch_text_local(url: str) -> str:
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
            # Add browser-like headers to avoid 403 errors
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            with httpx.Client(timeout=timeout, headers=headers, follow_redirects=True) as client:
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
    
    This function:
    1. Fetches the webpage content from the URL
    2. Extracts the main article text
    3. Generates a concise summary
    
    Args:
        url: The URL of the news webpage
        
    Returns:
        A summary of the webpage content
    """
    page_text = _fetch_text_local(url)
    return get_news_from_gemini(page_text)


def fetch_news_summary(url: str) -> str:
    """
    Fetch and summarize the news from the provided URL.
    
    Args:
        url: The URL of the news webpage
        
    Returns:
        A summary of the news article
    """
    summary = webpage_to_summary(url)
    print(f"Summary: {summary}")
    return summary

