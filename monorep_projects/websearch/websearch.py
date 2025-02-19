import requests
from bs4 import BeautifulSoup
from agno.agent import Agent
from agno.models.google import Gemini

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

def generate_summary(text, api_key):
    """
    Generate a summary of the provided text using Gemini.
    
    Args:
        text (str): The text content to summarize
        api_key (str): Your Google API key
        
    Returns:
        str: A summary of the text content, or error message if failed
    """
    try:
        model = Gemini(api_key=api_key)
        agent = Agent(model=model)
        
        prompt = f"""Please provide a concise summary of the following content. 
        Focus on the main points and key information:
        
        {text}"""
        
        response = agent.run(prompt)
        return response.content if hasattr(response, 'content') else str(response)
    except Exception as e:
        return f"Error generating summary: {str(e)}"

def summarize_url(url, api_key):
    """
    Fetch a webpage, extract its text content, and generate a summary using Gemini.
    
    Args:
        url (str): The URL of the webpage to summarize
        api_key (str): Your Google API key
        
    Returns:
        str: A summary of the webpage content
    """
    text = extract_text_from_url(url)
    if text.startswith("Error"):
        return text
    return generate_summary(text, api_key)

# # Example usage:
api_key = "AIzaSyAs8OV7InA2A1bNnTVvhJiaioAiylIAuYQ"  # Replace with your Google API key
url = "https://www.cnn.com/2025/02/19/economy/trump-inflation-is-back/index.html"
summary = summarize_url(url, api_key)
print(summary)

#print(extract_text_from_url("https://www.cnn.com/2025/02/19/economy/trump-inflation-is-back/index.html"))