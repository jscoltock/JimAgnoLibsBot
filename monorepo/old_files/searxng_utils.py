from agno.tools.searxng import Searxng
import json
import requests
from bs4 import BeautifulSoup
import time

def get_webpage_content(url: str) -> str:
    """Fetch and extract text content from a webpage"""
    try:
        # Add headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse HTML and extract text
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
            
        # Get text and clean it up
        text = soup.get_text(separator='\n', strip=True)
        # Remove excessive newlines
        lines = (line.strip() for line in text.splitlines())
        text = '\n'.join(line for line in lines if line)
        
        return text
        
    except Exception as e:
        return f"Error fetching webpage content: {str(e)}"

def pretty_print_results(results: str):
    """Helper function to print results in a readable format"""
    try:
        data = json.loads(results)
        print("\nFound", len(data.get('results', [])), "results:")
        for result in data.get('results', []):
            print("\n" + "="*80)
            print(f"Title: {result.get('title')}")
            print(f"URL: {result.get('url')}")
            
            # Print search result content
            print("\nSearch Result Summary:")
            print(result.get('content', 'No content available'))
            
            # Fetch and print full webpage content
            print("\nFull Webpage Content:")
            print("-" * 40)
            full_content = get_webpage_content(result['url'])
            print(full_content)
            
            # Additional metadata
            print("\nMetadata:")
            if 'engine' in result:
                print(f"Source Engine: {result['engine']}")
            if 'score' in result:
                print(f"Relevancy Score: {result['score']}")
            if 'category' in result:
                print(f"Category: {result['category']}")
            print("="*80)
            
            # Add a small delay between requests to be respectful
            time.sleep(1)
            
    except json.JSONDecodeError:
        print(results)  # Print raw results if not JSON

def main():
    # Initialize SearxNG with localhost instance
    searx = Searxng(
        host="http://localhost:4000",
        news=True,
        science=True,
        
    )

    # Test basic web search
    print("\n=== Testing Basic Web Search ===")
    results = searx.search("what did trump do today 2/18/2025", max_results=5)  # Reduced to 2 results since we're fetching full content
    pretty_print_results(results)

    # # Test news search
    # print("\n=== Testing News Search ===")
    # results = searx.news_search("artificial intelligence", max_results=2)
    # pretty_print_results(results)

    # # Test science search
    # print("\n=== Testing Science Search ===")
    # results = searx.science_search("quantum computing", max_results=2)
    # pretty_print_results(results)

    # # Test error handling with invalid host
    # print("\n=== Testing Error Handling ===")
    # invalid_searx = Searxng(host="https://invalid.example.com")
    # results = invalid_searx.search("test")
    # print(results)

def test_search():
    # Initialize SearxNG
    searxng = Searxng(
        host="http://localhost:4000",
        engines=[],
        fixed_max_results=5,
        news=True,
        science=True,
    )
    
    # Test queries
    queries = [
        "What did trump do today 2/18/2025",  # Simple query
        #"pip install -r requirements.txt multiple times",  # Query with flag
        #"If i run pip install -r requirements.txt multiple times is it additive?",  # Full question
    ]
    
    for query in queries:
        print(f"\nTesting query: {query}")
        try:
            results = searxng.search(query)
            print(f"Raw response type: {type(results)}")
            print(f"Raw response: {results[:200]}...")  # First 200 chars
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
    #test_search() 