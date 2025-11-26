from sqlalchemy.ext.asyncio import AsyncSession
from app.services.ollama_client import _ollama_chat

TOXICITY_SYSTEM_PROMPT = (
    "You are a toxicity detection model. Your task is to analyze the user's message and return a toxicity score from 0 to 100, where 0 is non-toxic and 100 is highly toxic. "
    "Consider insults, hate speech, and other forms of toxic language. "
    "Your response must be a single integer number and nothing else."
)

async def analyze_toxicity(
    session: AsyncSession, user_text: str
) -> int:
    """
    Analyzes user text for toxicity and returns a score from 0 to 100.
    """
    messages = [
        {"role": "system", "content": TOXICITY_SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]
    try:
        response = await _ollama_chat(messages, temperature=0.1, use_cache=True)
        return int(response)
    except (ValueError, TypeError):
        return 0 # Default to non-toxic if response is not an integer
    except Exception as e:
        # In case of Ollama error, default to non-toxic
        return 0