from os import getenv

from dotenv import load_dotenv

load_dotenv()

allowed_origins = getenv("ALLOWED_ORIGINS", "*").split(",")

RNNOISE_PATH = getenv("RNNOISE_PATH")

GROQ_API_KEY = getenv("GROQ_API_KEY")

GEMINI_API_KEY = getenv("GEMINI_API_KEY")
