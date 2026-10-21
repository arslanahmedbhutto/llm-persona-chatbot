"""Streamlit chat app with three LLM personas. Run with: streamlit run app.py"""
import os
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from chatbot.demo import load_conversation
from chatbot.engine import read_pdf, stream_reply
from chatbot.personas import PERSONAS, TURN_LIMIT

load_dotenv()
SAMPLE_DOC = Path(__file__).parent / "sample_docs" / "wellness_guide.pdf"
MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"]

st.set_page_config(page_title="Persona Chatbot", page_icon="💬", layout="centered")


def configured_api_key():
    """Key from Streamlit secrets (for deployment) or the environment / .env file (for local runs)."""
    try:
        if st.secrets.get("OPENAI_API_KEY"):
            return st.secrets["OPENAI_API_KEY"]
    except Exception:  # no secrets.toml
        pass
    return os.getenv("OPENAI_API_KEY", "")


@st.cache_data(show_spinner=False)
def sample_document():
    return read_pdf(str(SAMPLE_DOC)) if SAMPLE_DOC.exists() else ""


def transcript(persona, messages):
    lines = [f"{persona.name} conversation - {datetime.now():%Y-%m-%d %H:%M}", ""]
    for m in messages:
        lines.append(f"{'User' if m['role'] == 'user' else 'ChatBot'}: {m['content']}\n")
    return "\n".join(lines)


# ---------- State ----------
st.session_state.setdefault("histories", {key: [] for key in PERSONAS})
st.session_state.setdefault("pending", None)

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("## 💬 Persona Chatbot")
    st.caption("LangChain + OpenAI chatbots with distinct personalities")

    persona_key = st.radio(
        "Choose a chatbot",
        options=list(PERSONAS),
        format_func=lambda k: f"{PERSONAS[k].avatar}  {PERSONAS[k].name}",
        captions=[p.tagline for p in PERSONAS.values()],
    )
    persona = PERSONAS[persona_key]
    history = st.session_state.histories[persona_key]

    document = ""
    if persona.uses_document:
        st.markdown("#### 📄 Reference document")
        upload = st.file_uploader("Upload a PDF (up to ~5 pages works best)", type="pdf")
        if upload:
            document = read_pdf(upload)
            st.caption(f"Using **{upload.name}** ({len(document):,} characters)")
        else:
            document = sample_document()
            st.caption("Using the sample *wellness guide* PDF")

    with st.expander("⚙️ Model settings"):
        model = st.selectbox("Model", MODELS)
        temperature = st.slider("Creativity (temperature)", 0.0, 1.2, 0.7, 0.1)
        if not configured_api_key():
            st.text_input("OpenAI API key", type="password", key="user_api_key",
                          help="Stored only in this browser session.")

    user_turns = sum(m["role"] == "user" for m in history)
    st.progress(min(user_turns / TURN_LIMIT, 1.0), text=f"Turn {user_turns} of {TURN_LIMIT}")
    col1, col2 = st.columns(2)
    if col1.button("🗑️ New chat", use_container_width=True):
        st.session_state.histories[persona_key] = []
        st.rerun()
    col2.download_button("⬇️ Save chat", transcript(persona, history), use_container_width=True,
                         file_name=f"{persona.key}_{datetime.now():%Y%m%d_%H%M}.txt", disabled=not history)

api_key = configured_api_key() or st.session_state.get("user_api_key", "")

# ---------- Styling ----------
st.markdown(f"""
<style>
.persona-card {{
    display: flex; align-items: center; gap: 1rem;
    padding: 1rem 1.25rem; margin-bottom: 1rem; border-radius: 14px;
    background: linear-gradient(135deg, {persona.accent}22, {persona.accent}08);
    border: 1px solid {persona.accent}55;
}}
.persona-card .avatar {{ font-size: 2.6rem; line-height: 1; }}
.persona-card h2 {{ margin: 0; padding: 0; color: {persona.accent}; font-size: 1.6rem; }}
.persona-card p {{ margin: 0; opacity: .8; }}
[data-testid="stChatMessage"] {{ border-radius: 12px; }}
div.stButton > button[kind="secondary"] {{ border-radius: 20px; }}
</style>
<div class="persona-card">
  <div class="avatar">{persona.avatar}</div>
  <div><h2>{persona.name}</h2><p>{persona.tagline}</p></div>
</div>
""", unsafe_allow_html=True)

# ---------- Demo mode (no API key) ----------
if not api_key:
    st.info("**Demo mode:** add an OpenAI API key under *Model settings* in the sidebar to chat live, "
            "or load a real conversation recorded with this bot.", icon="🔑")
    if not history and st.button(f"▶️ Load a sample {persona.name} conversation"):
        st.session_state.histories[persona_key] = load_conversation(persona_key, max_exchanges=4)
        st.rerun()

# ---------- Conversation ----------
if not history and api_key:
    st.markdown(f"Say hello to **{persona.name}**, or try one of these:")
    cols = st.columns(len(persona.starters))
    for col, starter in zip(cols, persona.starters):
        if col.button(starter, use_container_width=True):
            st.session_state.pending = starter
            st.rerun()

for msg in history:
    with st.chat_message(msg["role"], avatar=persona.avatar if msg["role"] == "assistant" else "🧑"):
        st.markdown(msg["content"])

limit_reached = sum(m["role"] == "user" for m in history) >= TURN_LIMIT
placeholder = ("Add an API key in the sidebar to chat" if not api_key
               else "Session limit reached, start a new chat" if limit_reached
               else f"Message {persona.name}...")
typed = st.chat_input(placeholder, disabled=not api_key or limit_reached)
user_input = typed or st.session_state.pop("pending", None)

if user_input and api_key:
    with st.chat_message("user", avatar="🧑"):
        st.markdown(user_input)
    with st.chat_message("assistant", avatar=persona.avatar):
        try:
            reply = st.write_stream(stream_reply(persona, history, user_input, api_key=api_key,
                                                 model=model, temperature=temperature, document=document))
        except Exception as err:  # surface auth/network errors in the chat instead of crashing
            st.error(f"Couldn't get a reply: {err}")
            reply = None
    if reply:
        history.extend([{"role": "user", "content": user_input}, {"role": "assistant", "content": reply}])
