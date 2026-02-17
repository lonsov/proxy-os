"""
Streamlit frontend for PathFind AI — multiturn chatbot with tool-calling agent.
Run with:  streamlit run streamlit_app.py
"""

import os
import sys
import json
import io
import contextlib
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Ensure project root is on sys.path so app.py imports resolve
_PROJECT_ROOT = str(Path(__file__).resolve().parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

load_dotenv()

from app import JobAgent  # noqa: E402

# ------------------------------------------------------------------ #
# Page config
# ------------------------------------------------------------------ #

st.set_page_config(
    page_title="Pathfind AI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------ #
# Custom CSS
# ------------------------------------------------------------------ #

st.markdown("""
<style>
    /* Compact header */
    .block-container { padding-top: 2rem; }

    /* Chat message styling */
    .stChatMessage { max-width: 100%; }

    /* Status / progress text inside chat */
    .agent-status {
        color: #888;
        font-size: 0.85em;
        font-style: italic;
        padding: 2px 0;
    }

    /* Tool output blocks */
    .tool-output {
        background: #f8f9fa;
        border-left: 3px solid #4A90D9;
        padding: 12px 16px;
        border-radius: 4px;
        margin: 8px 0;
        font-family: 'Segoe UI', sans-serif;
        white-space: pre-wrap;
        word-wrap: break-word;
    }

    /* Job list cards */
    .job-card {
        background: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 6px 0;
        transition: border-color 0.2s;
    }
    .job-card:hover { border-color: #4A90D9; }

    /* Sidebar styling */
    section[data-testid="stSidebar"] .block-container { padding-top: 1rem; }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ #
# Session state initialization
# ------------------------------------------------------------------ #

def init_session_state():
    """Initialize all session state variables."""
    if "agent" not in st.session_state:
        st.session_state.agent = JobAgent()
    if "messages" not in st.session_state:
        # Chat display history (separate from agent's internal history)
        st.session_state.messages = []
    if "processing" not in st.session_state:
        st.session_state.processing = False


init_session_state()
agent: JobAgent = st.session_state.agent


# ------------------------------------------------------------------ #
# Sidebar
# ------------------------------------------------------------------ #

with st.sidebar:
    st.markdown("## 🤖 Pathfind AI")
    st.caption("Intelligent Job Search Assistant")
    st.divider()

    st.markdown("### What I can do")
    st.markdown("""
    - 🔍 **Search jobs** — "Find ML jobs at Google"
    - 🏢 **Research companies** — "Tell me about Anthropic"
    - 📄 **Tailor resume** — "Tailor my resume for this role"
    - ✉️ **Draft emails** — "Draft an email to the recruiter"
    - 👤 **Find recruiters** — "Find recruiter at OpenAI"
    """)

    st.divider()

    # Context status
    st.markdown("### 📦 Current Context")
    selected_job = agent.context_store.get("selected_job") or {}
    if isinstance(selected_job, dict) and selected_job.get("title") and selected_job["title"] != "N/A":
        st.success(f"**Selected Job:** {selected_job.get('title', 'N/A')}")
        st.caption(f"at {selected_job.get('company', 'N/A')}")
        if selected_job.get("jd_text"):
            st.caption(f"JD: {len(selected_job['jd_text'])} chars ✅")
        else:
            st.caption("JD: not extracted")
    else:
        st.info("No job selected yet")

    last_jobs = agent.context_store.get("last_jobs") or {}
    if isinstance(last_jobs, dict) and last_jobs.get("jobs"):
        st.caption(f"Last search: {len(last_jobs['jobs'])} jobs found")

    st.divider()

    # Actions
    if st.button("🔄 Reset Conversation", use_container_width=True):
        agent.reset()
        # Also reset awaiting flags
        agent.awaiting_job_selection = False
        agent.awaiting_jd_text = False
        agent.awaiting_email_jd_link = False
        agent.awaiting_job_search_metadata = False
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.caption("Powered by Llama 3 70B + Browser Use")


# ------------------------------------------------------------------ #
# Helper: capture stdout from agent (progress prints)
# ------------------------------------------------------------------ #

def run_agent_chat(user_input: str) -> tuple[str, str]:
    """
    Run agent.chat() and capture any stdout prints (progress messages)
    separately from the returned response text.
    Returns (response, captured_stdout).
    """
    stdout_capture = io.StringIO()
    with contextlib.redirect_stdout(stdout_capture):
        response = agent.chat(user_input)
    return response, stdout_capture.getvalue()


# ------------------------------------------------------------------ #
# Helper: detect if response contains a job list for interactive selection
# ------------------------------------------------------------------ #

def is_job_list_response(response: str) -> bool:
    """Check if the agent response is a numbered job list awaiting selection."""
    return agent.awaiting_job_selection and "Reply with a number" in response


def parse_job_list(response: str) -> tuple[str, list[dict]]:
    """Split header text from job list, return jobs from context."""
    jobs = []
    last_jobs = agent.context_store.get("last_jobs") or {}
    if isinstance(last_jobs, dict):
        jobs = last_jobs.get("jobs", [])
    header = response.split("\n")[0] if response else ""
    return header, jobs


def render_job_search_metadata_form() -> tuple[bool, str]:
    """Render structured job-search metadata form and return (submitted, payload)."""
    with st.expander("🔎 Complete Job Search Filters", expanded=True):
        st.caption("Fill this once, then I will run the search automatically.")
        with st.form("job_search_metadata_form", clear_on_submit=False):
            role = st.text_input("Role (required)", placeholder="e.g., Machine Learning Engineer")
            company = st.text_input("Company (optional)", placeholder="e.g., OpenAI")
            location = st.text_input("Location (optional)", value="", placeholder="e.g., San Francisco, CA or Remote")
            experience_level = st.selectbox(
                "Experience Level",
                options=["", "entry", "mid", "senior", "lead", "staff"],
                index=0,
            )
            job_type = st.selectbox(
                "Job Type",
                options=["", "full-time", "contract", "internship", "part-time"],
                index=0,
            )
            work_mode = st.selectbox(
                "Work Mode",
                options=["", "remote", "hybrid", "onsite"],
                index=0,
            )
            skills_keywords = st.text_input(
                "Must-have Skills/Keywords",
                placeholder="e.g., python, llms, pytorch",
            )
            exclude_keywords = st.text_input(
                "Exclude Keywords",
                placeholder="e.g., manager, director",
            )
            posted_within_days = st.text_input(
                "Posted Within (days, optional)",
                value="",
                placeholder="e.g., 7",
            )

            submitted = st.form_submit_button("Run Job Search", use_container_width=True)
            if not submitted:
                return False, ""

            payload = (
                f"role: {role}\n"
                f"company: {company}\n"
                f"location: {location}\n"
                f"experience_level: {experience_level}\n"
                f"job_type: {job_type}\n"
                f"work_mode: {work_mode}\n"
                f"skills_keywords: {skills_keywords}\n"
                f"exclude_keywords: {exclude_keywords}\n"
                f"posted_within_days: {posted_within_days}"
            )
            return True, payload


# ------------------------------------------------------------------ #
# Main chat area
# ------------------------------------------------------------------ #

st.markdown("# 🤖 PathFind AI")
st.caption("Search jobs, research companies, tailor resumes, draft emails — all in one conversation.")

# Display chat history
for msg in st.session_state.messages:
    role = msg["role"]
    content = msg["content"]
    with st.chat_message("user" if role == "user" else "assistant", avatar="👤" if role == "user" else "🤖"):
        # Check if this message has special rendering
        msg_type = msg.get("type", "text")

        if msg_type == "job_list":
            st.markdown(content)
        elif msg_type == "progress":
            st.markdown(f'<div class="agent-status">{content}</div>', unsafe_allow_html=True)
        else:
            st.markdown(content)

# Chat input
if prompt := st.chat_input("Ask me anything about jobs, companies, resumes...", disabled=st.session_state.processing):
    # Display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # Process with agent
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Thinking..."):
            response, progress_output = run_agent_chat(prompt)

        # Show progress output if any (search status, etc.)
        if progress_output.strip():
            # Clean up progress lines — filter out debug logs, keep user-facing ones
            progress_lines = []
            skip_block = False
            for line in progress_output.strip().split("\n"):
                stripped = line.strip()
                # Skip debug log blocks
                if "🧭 DEBUG LOG" in stripped or "=" * 40 in stripped:
                    skip_block = True
                    continue
                if skip_block:
                    if stripped.startswith("="):
                        skip_block = False
                    continue
                # Keep user-facing progress lines
                if stripped and any(e in stripped for e in ("🔍", "📊", "💬", "✅", "❌", "🏢", "📄", "📧", "👤", "🔎")):
                    progress_lines.append(stripped)

            if progress_lines:
                progress_text = "\n".join(progress_lines)
                st.caption(progress_text)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": progress_text,
                    "type": "progress",
                })

        # Render the main response
        if is_job_list_response(response):
            # Interactive job selection with buttons
            header, jobs = parse_job_list(response)

            st.markdown("**Here are the jobs I found. Click one to select:**")

            for i, job in enumerate(jobs, 1):
                title = job.get("jobTitle") or job.get("title") or "Unknown"
                company = job.get("companyName") or job.get("company") or "Unknown"
                location = job.get("location") or "N/A"
                url = job.get("applicationUrl") or job.get("url") or ""
                salary = job.get("salary") or ""
                experience = job.get("experienceLevel") or ""

                col1, col2 = st.columns([5, 1])
                with col1:
                    label = f"**{i}. {title}** — {company}"
                    if location != "N/A":
                        label += f" 📍 {location}"
                    if salary:
                        label += f" 💰 {salary}"
                    if experience:
                        label += f" | {experience}"
                    st.markdown(label)
                    if url:
                        st.caption(f"🔗 {url}")
                with col2:
                    if st.button(f"Select", key=f"job_{i}"):
                        # Send the selection number to agent
                        st.session_state.messages.append({"role": "user", "content": f"Selected job #{i}"})
                        with st.spinner(f"Selecting job {i} and extracting JD..."):
                            sel_response, sel_progress = run_agent_chat(str(i))
                        st.session_state.messages.append({"role": "assistant", "content": sel_response})
                        st.rerun()

            # Also store the raw response for history
            st.session_state.messages.append({
                "role": "assistant",
                "content": response,
                "type": "job_list",
            })
        else:
            # Regular text response
            display_response = response
            if getattr(agent, "awaiting_job_search_metadata", False) and response.startswith("Before I run job search"):
                display_response = "Please complete the job search fields below."
            st.markdown(display_response)
            st.session_state.messages.append({"role": "assistant", "content": display_response})

# Persistent job-search metadata form: always shown while agent is waiting.
if getattr(agent, "awaiting_job_search_metadata", False):
    with st.chat_message("assistant", avatar="🤖"):
        submitted, form_payload = render_job_search_metadata_form()
        if submitted:
            st.session_state.messages.append({
                "role": "user",
                "content": "Submitted job search filters via form.",
            })
            with st.spinner("Running job search..."):
                form_response, form_progress = run_agent_chat(form_payload)

            if form_progress.strip():
                progress_lines = []
                skip_block = False
                for line in form_progress.strip().split("\n"):
                    stripped = line.strip()
                    if "🧭 DEBUG LOG" in stripped or "=" * 40 in stripped:
                        skip_block = True
                        continue
                    if skip_block:
                        if stripped.startswith("="):
                            skip_block = False
                        continue
                    if stripped and any(e in stripped for e in ("🔍", "📊", "💬", "✅", "❌", "🏢", "📄", "📧", "👤", "🔎")):
                        progress_lines.append(stripped)
                if progress_lines:
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": "\n".join(progress_lines),
                        "type": "progress",
                    })

            st.session_state.messages.append({"role": "assistant", "content": form_response})
            st.rerun()


# ------------------------------------------------------------------ #
# Quick action buttons (shown when no conversation yet)
# ------------------------------------------------------------------ #

if not st.session_state.messages:
    st.divider()
    st.markdown("### 🚀 Quick Start")
    cols = st.columns(4)
    quick_actions = [
        ("🔍 Search Jobs", "Find ML engineer jobs at Google"),
        ("🏢 Research Company", "Research about OpenAI"),
        ("📄 Tailor Resume", "Tailor my resume"),
        ("✉️ Draft Email", "Draft an email"),
    ]
    for col, (label, prompt_text) in zip(cols, quick_actions):
        with col:
            if st.button(label, use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": prompt_text})
                with st.spinner("Processing..."):
                    response, _ = run_agent_chat(prompt_text)
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.rerun()
