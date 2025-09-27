from google import genai
from dotenv import load_dotenv
import os

# env variable
load_dotenv()

# Get API key 
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env file")


client = genai.Client(api_key=api_key)

# Test call
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Who is Prof Gaurav Harit?"
)

print("Gemini Response:", response.text)