"""Saraiki Student Council Assistant - Superior University Gold Campus.

Features: sign up / sign in, AI chat assistant (English / Urdu / Roman Urdu),
council team directory, upcoming events and an About page.
"""

from __future__ import annotations

import base64
import html
import json
import os
from datetime import date, datetime
from pathlib import Path

import anthropic
import streamlit as st

import db

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 1024
MAX_HISTORY_MESSAGES = 20
MAX_USER_MESSAGES_PER_SESSION = 40  # protects the API budget
MAX_FAILED_LOGINS = 5

PAGE_CHAT, PAGE_TEAM, PAGE_EVENTS, PAGE_ABOUT = (
    "💬 Chat Assistant",
    "👥 Our Team",
    "📅 Upcoming Events",
    "ℹ️ About the Council",
)
PAGES = [PAGE_CHAT, PAGE_TEAM, PAGE_EVENTS, PAGE_ABOUT]

QUICK_QUESTIONS = [
    "Who is the Chairman and how can I contact him?",
    "I want help with admission. Who should I contact?",
    "Mid-term paper ki preparation ke liye kis se rabta karun?",
    "What upcoming events are there?",
]

SYSTEM_PROMPT_TEMPLATE = """You are the official virtual assistant of the {council_name} \
({campus}), helping students and visitors.

Rules:
1. Answer ONLY using the information below. Never invent names, phone numbers, fees, \
dates or policies. If something is not in the information, say you don't have it and \
suggest contacting the Chairman or the General Secretary.
2. Reply in the language the user writes in: English, Urdu script, or Roman Urdu. If the \
user writes in Saraiki, reply in simple Urdu or Roman Urdu.
3. When the user asks who to contact, choose the best person using the "Can help with" \
field. Give their name, role and phone number. If the phone number says "not provided \
yet", say the number has not been added yet and suggest contacting the Chairman or \
General Secretary through the council.
4. For admission questions, recommend the Chairman or the General Secretary.
5. For events, list only items under UPCOMING EVENTS. If there are none, say no events \
have been announced yet.
6. For university fees, deadlines and admission dates, remind users to confirm on the \
official university website.
7. Be polite, short and clear. Use bullet points when listing several items.
8. Stay on topic. Politely decline requests unrelated to the council or the university.

TODAY'S DATE: {today}

COUNCIL
- Name: {council_name}
- Campus: {campus}
- Current cabinet: {cabinet}
- Founder: {founder}
- Founded: {founded}
- Purpose:
{purpose}

MEMBERS (cabinet {cabinet})
{members}

UPCOMING EVENTS
{events}

EXTRA INFORMATION
{knowledge_base}
"""


# ----------------------------------------------------------------------------
# Data helpers
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_json(name: str):
    path = BASE_DIR / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


@st.cache_data(show_spinner=False)
def load_text(name: str) -> str:
    path = BASE_DIR / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def council_data() -> dict:
    return load_json("council_data.json")


def get_events() -> tuple[list[dict], list[dict]]:
    """Return (upcoming, past) events sorted by date."""
    items = []
    for event in load_json("events.json") or []:
        try:
            when = datetime.strptime(event["date"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            continue
        items.append({**event, "_date": when})
    items.sort(key=lambda e: e["_date"])
    today = date.today()
    upcoming = [e for e in items if e["_date"] >= today]
    past = [e for e in items if e["_date"] < today][::-1]
    return upcoming, past


def format_event_line(event: dict) -> str:
    parts = [
        f"- {event.get('title', 'Untitled')} | {event['_date'].strftime('%A, %d %B %Y')}",
        f"time: {event.get('time', 'TBA')}",
        f"venue: {event.get('venue', 'TBA')}",
    ]
    if event.get("description"):
        parts.append(f"details: {event['description']}")
    if event.get("contact_role"):
        parts.append(f"contact: {event['contact_role']}")
    return " | ".join(parts)


def build_system_prompt() -> str:
    data = council_data()
    council, members = data["council"], data["members"]
    member_lines = []
    for i, m in enumerate(members, 1):
        phone = m.get("phone") or "not provided yet"
        member_lines.append(
            f"{i}. {m['name']} | Role: {m['role']} | Phone: {phone} | "
            f"Can help with: {m['help_with']}"
        )
    upcoming, _ = get_events()
    events_text = (
        "\n".join(format_event_line(e) for e in upcoming)
        if upcoming
        else "No upcoming events have been announced yet."
    )
    return SYSTEM_PROMPT_TEMPLATE.format(
        council_name=council["name"],
        campus=council["campus"],
        cabinet=council["cabinet"],
        founder=council["founder"],
        founded=council["founded"],
        purpose="\n".join(f"  * {p}" for p in council["purpose"]),
        members="\n".join(member_lines),
        events=events_text,
        knowledge_base=load_text("knowledge_base.md") or "None.",
        today=date.today().strftime("%A, %d %B %Y"),
    )


def get_api_key() -> str | None:
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        return os.getenv("ANTHROPIC_API_KEY")


@st.cache_resource(show_spinner=False)
def get_client(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key)


def stream_reply(client: anthropic.Anthropic, messages: list[dict]):
    history = messages[-MAX_HISTORY_MESSAGES:]
    while history and history[0]["role"] != "user":
        history = history[1:]
    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=build_system_prompt(),
        messages=history,
    ) as stream:
        for text in stream.text_stream:
            yield text


# ----------------------------------------------------------------------------
# UI building blocks
# ----------------------------------------------------------------------------
def esc(value: str) -> str:
    return html.escape(str(value), quote=True)


def render_hero(title: str, subtitle: str, badge: str | None = None) -> None:
    badge_html = f'<div class="hero-badge">{esc(badge)}</div>' if badge else ""
    st.markdown(
        f'<div class="hero"><div class="hero-title">🎓 {esc(title)}</div>'
        f'<div class="hero-sub">{esc(subtitle)}</div>{badge_html}</div>',
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    c = council_data()["council"]
    st.markdown(
        f'<div class="app-footer">{esc(c["name"])} · {esc(c["campus"])}</div>',
        unsafe_allow_html=True,
    )


def initials(name: str) -> str:
    return "".join(w[0] for w in name.split()[:2]).upper()


def avatar_html(member: dict) -> str:
    """Use photos/<member id>.jpg|jpeg|png|webp if it exists, otherwise initials."""
    for ext, mime in (("jpg", "jpeg"), ("jpeg", "jpeg"), ("png", "png"), ("webp", "webp")):
        path = BASE_DIR / "photos" / f"{member['id']}.{ext}"
        if path.exists():
            data = base64.b64encode(path.read_bytes()).decode()
            return f'<div class="avatar"><img src="data:image/{mime};base64,{data}"></div>'
    return f'<div class="avatar">{esc(initials(member["name"]))}</div>'


def member_card(member: dict, featured: bool = False) -> str:
    phone = member.get("phone", "").strip()
    phone_html = (
        f'<a class="phone" href="tel:{esc(phone)}">📞 {esc(phone)}</a>' if phone else ""
    )
    cls = "member-card featured" if featured else "member-card"
    return (
        f'<div class="{cls}">{avatar_html(member)}'
        f'<div class="member-name">{esc(member["name"])}</div>'
        f'<div class="member-role">{esc(member["role"])}</div>{phone_html}</div>'
    )


# ----------------------------------------------------------------------------
# Authentication
# ----------------------------------------------------------------------------
def render_auth() -> None:
    c = council_data()["council"]
    render_hero(
        c["name"],
        f"{c['campus']} · Cabinet {c['cabinet']}",
        "Sign in to chat with the council assistant",
    )
    _, mid, _ = st.columns([1, 3, 1])
    with mid:
        tab_in, tab_up = st.tabs(["Sign in", "Create account"])

        with tab_in:
            with st.form("signin_form"):
                email = st.text_input("Email", key="signin_email")
                password = st.text_input("Password", type="password", key="signin_pw")
                submitted = st.form_submit_button("Sign in", use_container_width=True)
            if submitted:
                if st.session_state.get("failed_logins", 0) >= MAX_FAILED_LOGINS:
                    st.error("Too many failed attempts. Please reload the page and try again.")
                else:
                    user = db.authenticate(email, password)
                    if user:
                        st.session_state["user"] = user
                        st.session_state["failed_logins"] = 0
                        st.rerun()
                    st.session_state["failed_logins"] = st.session_state.get("failed_logins", 0) + 1
                    st.error("Incorrect email or password.")

        with tab_up:
            with st.form("signup_form"):
                full_name = st.text_input("Full name", key="signup_name")
                email = st.text_input("Email", key="signup_email")
                password = st.text_input(
                    "Password (min. 8 characters)", type="password", key="signup_pw"
                )
                confirm = st.text_input("Confirm password", type="password", key="signup_pw2")
                submitted = st.form_submit_button("Create account", use_container_width=True)
            if submitted:
                if password != confirm:
                    st.error("Passwords do not match.")
                else:
                    ok, message = db.create_user(full_name, email, password)
                    if ok:
                        st.session_state["user"] = db.authenticate(email, password)
                        st.rerun()
                    st.error(message)
    render_footer()


# ----------------------------------------------------------------------------
# Pages
# ----------------------------------------------------------------------------
def render_sidebar() -> str:
    c = council_data()["council"]
    user = st.session_state["user"]
    with st.sidebar:
        st.markdown(
            f'<div class="side-brand">🎓 {esc(c["name"])}<br>'
            f'<small>{esc(c["campus"])}</small></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="side-user">Signed in as<br><b>{esc(user["full_name"])}</b></div>',
            unsafe_allow_html=True,
        )
        page = st.radio("Navigate", PAGES, key="nav", label_visibility="collapsed")
        st.divider()
        if page == PAGE_CHAT and st.button("🗑️ Clear chat", use_container_width=True):
            st.session_state["messages"] = []
            st.rerun()
        if st.button("Sign out", use_container_width=True):
            for key in ("user", "messages", "pending_prompt"):
                st.session_state.pop(key, None)
            st.rerun()
    return page


def page_chat() -> None:
    c = council_data()["council"]
    render_hero(
        "Council Assistant",
        "Ask about admissions, exam guidance, members, contacts and events",
        f"{c['campus']} · Cabinet {c['cabinet']}",
    )

    api_key = get_api_key()
    if not api_key:
        st.error(
            "The API key is missing. Add `ANTHROPIC_API_KEY` to your Streamlit secrets "
            "(see README.md) and reload the app."
        )
        return
    client = get_client(api_key)

    messages = st.session_state.setdefault("messages", [])

    typed = st.chat_input("Ask in English, Urdu or Roman Urdu...")
    prompt = typed or st.session_state.pop("pending_prompt", None)
    if prompt:
        messages.append({"role": "user", "content": prompt})

    if not messages:
        with st.chat_message("assistant", avatar="🎓"):
            st.write(
                "Assalam-o-Alaikum! I'm the Saraiki Student Council assistant. "
                "Ask me about admissions, exam preparation, council members, "
                "contact numbers or upcoming events. / Aap Urdu ya Roman Urdu mein "
                "bhi sawal pooch sakte hain."
            )
        cols = st.columns(2)
        for i, question in enumerate(QUICK_QUESTIONS):
            if cols[i % 2].button(question, use_container_width=True, key=f"quick_{i}"):
                st.session_state["pending_prompt"] = question
                st.rerun()

    for msg in messages:
        with st.chat_message(msg["role"], avatar="🎓" if msg["role"] == "assistant" else "🧑"):
            st.markdown(msg["content"])

    if prompt:
        user_count = sum(1 for m in messages if m["role"] == "user")
        with st.chat_message("assistant", avatar="🎓"):
            if user_count > MAX_USER_MESSAGES_PER_SESSION:
                reply = (
                    "You have reached the message limit for this session. "
                    "Please sign out and sign in again, or contact the council directly."
                )
                st.warning(reply)
            else:
                try:
                    reply = st.write_stream(stream_reply(client, messages))
                except anthropic.AuthenticationError:
                    reply = "Authentication failed. Please check the API key."
                    st.error(reply)
                except anthropic.RateLimitError:
                    reply = "The service is busy right now. Please try again in a moment."
                    st.warning(reply)
                except anthropic.APIError:
                    reply = "Something went wrong while contacting the AI service. Please try again."
                    st.error(reply)
        messages.append({"role": "assistant", "content": reply})


def page_team() -> None:
    data = council_data()
    c, members = data["council"], data["members"]
    render_hero("Our Team", f"Cabinet {c['cabinet']} · {c['campus']}")

    query = st.text_input("Search by name or role", placeholder="e.g. Chairman, Maaz, Media")
    if query.strip():
        q = query.strip().lower()
        found = [m for m in members if q in m["name"].lower() or q in m["role"].lower()]
        if not found:
            st.markdown('<div class="empty-state">No member found.</div>', unsafe_allow_html=True)
        for i in range(0, len(found), 3):
            for col, m in zip(st.columns(3), found[i : i + 3]):
                col.markdown(member_card(m), unsafe_allow_html=True)
    else:
        _, centre, _ = st.columns([1, 1, 1])
        centre.markdown(member_card(members[0], featured=True), unsafe_allow_html=True)
        rest = members[1:]
        for i in range(0, len(rest), 3):
            for col, m in zip(st.columns(3), rest[i : i + 3]):
                col.markdown(member_card(m), unsafe_allow_html=True)
    render_footer()


def event_card(event: dict) -> str:
    meta = f"📅 {event['_date'].strftime('%A, %d %B %Y')}"
    if event.get("time"):
        meta += f" · 🕒 {esc(event['time'])}"
    if event.get("venue"):
        meta += f" · 📍 {esc(event['venue'])}"
    desc = f'<div class="event-desc">{esc(event["description"])}</div>' if event.get("description") else ""
    contact = (
        f'<div class="event-meta">Contact: {esc(event["contact_role"])}</div>'
        if event.get("contact_role")
        else ""
    )
    return (
        f'<div class="event-card"><div class="event-title">{esc(event.get("title", "Event"))}</div>'
        f'<div class="event-meta">{meta}</div>{desc}{contact}</div>'
    )


def page_events() -> None:
    render_hero("Upcoming Events", "Stay updated with council programs and activities")
    upcoming, past = get_events()
    if upcoming:
        for event in upcoming:
            st.markdown(event_card(event), unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="empty-state">No upcoming events have been announced yet.<br>'
            "Please check back soon!</div>",
            unsafe_allow_html=True,
        )
    if past:
        with st.expander(f"Past events ({len(past)})"):
            for event in past:
                st.markdown(event_card(event), unsafe_allow_html=True)
    render_footer()


def page_about() -> None:
    c = council_data()["council"]
    render_hero(f"About {c['name']}", c["campus"], f"Cabinet {c['cabinet']}")
    st.markdown(
        f'<div class="info-card"><b>Founder:</b> {esc(c["founder"])}<br>'
        f'<b>Founded:</b> {esc(c["founded"])}<br>'
        f'<b>Campus:</b> {esc(c["campus"])}</div>',
        unsafe_allow_html=True,
    )
    purpose = "".join(f"<li>{esc(p)}</li>" for p in c["purpose"])
    st.markdown(
        f'<div class="info-card"><b>Our purpose</b><ul>{purpose}</ul></div>',
        unsafe_allow_html=True,
    )
    render_footer()


# ----------------------------------------------------------------------------
# App entry point
# ----------------------------------------------------------------------------
st.set_page_config(page_title="Saraiki Student Council", page_icon="🎓", layout="centered")
css_path = BASE_DIR / "styles.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

db.init_db()

if not st.session_state.get("user"):
    render_auth()
    st.stop()

current_page = render_sidebar()
{PAGE_CHAT: page_chat, PAGE_TEAM: page_team, PAGE_EVENTS: page_events, PAGE_ABOUT: page_about}[
    current_page
]()
