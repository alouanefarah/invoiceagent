"""
Client Groq centralisé.
Groq est gratuit, rapide, et supporte llama-3.3-70b multilingue FR/AR.
"""
import httpx
from groq import Groq
from app.core.config import settings

_client: Groq | None = None


def get_client() -> Groq:
    global _client
    if _client is None:
        # trust_env=False : ignore les variables de proxy système (HTTP_PROXY, etc.)
        # qui peuvent contenir des caractères non-ASCII et faire planter l'encodage des headers.
        http_client = httpx.Client(trust_env=False)
        _client = Groq(api_key=settings.GROQ_API_KEY, http_client=http_client)
    return _client


def chat(prompt: str) -> str:
    """Appel simple texte → texte via Groq."""
    client = get_client()
    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=4096,
    )
    return response.choices[0].message.content
