"""LangChain chat engine: builds the prompt from a persona, short-term memory and an optional document."""
from io import BytesIO

import pdfplumber
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .personas import TURN_LIMIT, Persona

MEMORY_TURNS = 10          # how many past exchanges the bot remembers
MAX_DOCUMENT_CHARS = 12000  # keeps long PDFs from blowing up token costs


def read_pdf(file) -> str:
    """Extract the text from a PDF given as a path or an uploaded file."""
    source = BytesIO(file.read()) if hasattr(file, "read") else file
    with pdfplumber.open(source) as pdf:
        text = "\n".join(page.extract_text(x_tolerance=1) or "" for page in pdf.pages)
    return text[:MAX_DOCUMENT_CHARS]


def build_system_prompt(persona: Persona, document: str = "") -> str:
    prompt = persona.system_prompt.replace("{turn_limit}", str(TURN_LIMIT))
    if persona.uses_document:
        prompt = prompt.replace("{document}", document.strip() or "(No document provided.)")
    return prompt


def build_messages(persona: Persona, history: list, user_input: str, document: str = "") -> list:
    """history is a list of {"role": "user" | "assistant", "content": str} dicts."""
    messages = [SystemMessage(build_system_prompt(persona, document))]
    for msg in history[-MEMORY_TURNS * 2:]:
        cls = HumanMessage if msg["role"] == "user" else AIMessage
        messages.append(cls(msg["content"]))
    messages.append(HumanMessage(user_input))
    return messages


def stream_reply(persona: Persona, history: list, user_input: str, *, api_key: str,
                 model: str = "gpt-4o-mini", temperature: float = 0.7, document: str = ""):
    """Yield the reply token by token."""
    llm = ChatOpenAI(model=model, temperature=temperature, api_key=api_key)
    for chunk in llm.stream(build_messages(persona, history, user_input, document)):
        if chunk.content:
            yield chunk.content
