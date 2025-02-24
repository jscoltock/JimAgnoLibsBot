"""
This file contains three main functions that work together to perform web research and summarization: 
extract_text_from_url() scrapes and cleans text content from a given webpage, 
search_searxng() performs web searches using a local SearXNG instance and returns URLs with descriptions, 
and summarize_web_search() combines these functions by searching for a query, extracting text from the found URLs, 
and using Gemini to generate a summary of the collected web content.
NOTE: the web search assumes an llm with large context window like gemini. Other models may not
 accept the context window size required to summarize the web search.
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict

# next two only for the example usage
from dotenv import load_dotenv 
import google.generativeai as genai  

# Load environment variables from .env file only for the example usage
load_dotenv()

def extract_text_from_url(url):
    """
    Fetch a webpage and extract its text content.
    
    Args:
        url (str): The URL of the webpage to extract text from
        
    Returns:
        str: The extracted text content, or error message if failed
    """
    # Fetch the webpage
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
    except requests.RequestException as e:
        return f"Error fetching URL: {str(e)}"
    
    # Parse the HTML and extract text
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.decompose()
    
    # Get text content
    text = soup.get_text(separator=' ', strip=True)
    
    # Clean up whitespace
    return ' '.join(text.split())


def search_searxng(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """Search SearXNG running on localhost and return results.
    
    Args:
        query: The search query string
        num_results: Number of results to return (default 5)
        
    Returns:
        List of dictionaries containing 'url' and 'description' for each result
        
    Example:
        results = search_searxng("python programming", 3)
        for result in results:
            print(f"URL: {result['url']}")
            print(f"Description: {result['description']}\n")
    """
    # SearXNG API endpoint
    base_url = "http://localhost:4000/search"
    
    # Prepare parameters
    params = {
        'q': query,
        'format': 'json',
        'pageno': 1,
        'language': 'en'
    }
    
    try:
        # Make the request
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # Raise exception for bad status codes
        
        # Parse JSON response
        data = response.json()
        
        # Extract results
        results = []
        for item in data.get('results', [])[:num_results]:
            result = {
                'url': item.get('url', ''),
                'description': item.get('content', '')
            }
            results.append(result)
            
        return results
        
    except requests.RequestException as e:
        print(f"Error making request to SearXNG: {e}")
        return []
    except ValueError as e:
        print(f"Error parsing JSON response: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error: {e}")
        return []


def summarize_web_search(query: str, num_pages: int = 3) -> str:
    """
    Search for web pages, extract their content, and return an AI-generated summary.
    
    Args:
        query (str): The search query
        num_pages (int): Number of web pages to search and summarize
        
    Returns:
        str: AI-generated summary of the web pages' content
    """
    # Configure Gemini
    genai.configure()
    
    # Initialize Gemini model
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    # Get search results
    results = search_searxng(query, num_pages)
    
    # Extract text from each URL
    all_text = []
    for result in results:
        text = extract_text_from_url(result['url'])
        if not text.startswith('Error'):  # Only include successful extractions
            all_text.append(text)
    
    # Combine all text
    combined_text = "\n\n".join(all_text)
    
    # Create prompt with query context
    prompt = f"""Based on the following web content, {query}

Content:
{combined_text}"""
    
    # Generate summary using Gemini
    response = model.generate_content(prompt)
    return response.text


# ############################ Example usage of all functions ###################################
 
# print("Example of web search (returns URL's)")
# results = search_searxng("python programming", 3)
# for i, result in enumerate(results, 1):
#     print(result['url'])
#     print(result['description'])

# input()

# print("Example of extracting text from a url")
# print(extract_text_from_url("https://www.cnn.com/2025/02/19/economy/trump-inflation-is-back/index.html"))

# input()

# print("Example of iterating through results of web search and extracting text from each url")
# results = search_searxng("python programming", 3)
# for result in results:
#     print(extract_text_from_url(result['url']))

# input() 

# print("Example of summarizing web search  (does web search, extracts text from each url, and summarizes the text using AI)")
# summary = summarize_web_search("What is the best coffee maker under $100?", 10)
# print(summary)
