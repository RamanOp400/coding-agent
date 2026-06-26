import os 
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from dotenv import load_dotenv
load_dotenv()
llm = ChatNVIDIA(
  model="openai/gpt-oss-120b",
  api_key=os.getenv("NVIDIA_API_KEY"),
  temperature=1,
  top_p=0.95,
  max_completion_tokens=8192,
)
