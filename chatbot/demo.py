"""Load recorded conversations so the app can be explored without an API key."""
import re
from pathlib import Path

CONVERSATIONS_DIR = Path(__file__).resolve().parent.parent / "sample_conversations"
TURN = re.compile(r"^(User|ChatBot)\s*:\s?", re.MULTILINE)


def load_conversation(persona_key: str, max_exchanges: int = None) -> list:
    """Parse a 'User: ... / ChatBot: ...' log into chat messages."""
    path = CONVERSATIONS_DIR / f"{persona_key}.txt"
    if not path.exists():
        return []
    parts = TURN.split(path.read_text(encoding="utf-8"))
    messages = []
    for speaker, text in zip(parts[1::2], parts[2::2]):
        text = text.strip().strip('"').strip()
        if text:
            messages.append({"role": "user" if speaker == "User" else "assistant", "content": text})
    return messages[:max_exchanges * 2] if max_exchanges else messages
