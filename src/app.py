import streamlit as st

from config import APP_TITLE, APP_SUBTITLE, AVAILABLE_MODELS, DEFAULT_MODEL
from llm import get_response
from token_tracker import SessionTracker
from usage_store import get_usage_summary


st.set_page_config(page_title=APP_TITLE, page_icon="📊", layout="wide")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "tracker" not in st.session_state:
    st.session_state.tracker = SessionTracker()


with st.sidebar:
    st.title("⚙️ Settings")

    selected_model = st.selectbox(
        "Select Model",
        list(AVAILABLE_MODELS.keys()),
        format_func=lambda x: AVAILABLE_MODELS[x],
        index=list(AVAILABLE_MODELS.keys()).index(DEFAULT_MODEL),
    )

    st.divider()

    st.markdown("### 📁 Data Source")
    st.info("Connected: `donors.db`")

    st.markdown("### 📊 Session Usage")
    st.markdown(st.session_state.tracker.format_sidebar())

    st.markdown("### 🗄️ App Usage")
    try:
        app_usage = get_usage_summary()
        st.caption(f"API calls: {app_usage.get('total_api_calls', 0)}")
        st.caption(f"Sessions: {app_usage.get('total_sessions', 0)}")
        st.caption(f"Input tokens: {app_usage.get('total_input_tokens', 0):,}")
        st.caption(f"Output tokens: {app_usage.get('total_output_tokens', 0):,}")
        st.caption(f"Estimated cost: ${app_usage.get('estimated_total_cost_usd', 0):.4f}")
    except Exception as e:
        st.warning(f"Usage stats unavailable: {e}")

    st.divider()

    st.markdown("### 🎯 Quick Filters")
    donor_status_filter = st.selectbox(
        "Default donor status view",
        ["All", "active", "lapsed", "prospect"],
        index=0,
    )
    sort_choice = st.selectbox(
        "Default ranking",
        ["total_gifts", "average_gift", "wealth_score", "last_gift_date"],
        index=0,
    )

    st.caption("Quick filters are currently for reference in the interface.")

    st.divider()

    st.markdown("### ❓ Frequently Asked Questions")
    with st.expander("What can I ask here?"):
        st.markdown(
            "- Show top donors overall\n"
            "- Show top donors in ZIP 10027\n"
            "- Find lapsed donors worth re-engaging\n"
            "- Identify high-potential prospects\n"
            "- Summarize geographic donor distribution\n"
            "- Show donor C000015"
        )

    with st.expander("Why are some answers short?"):
        st.markdown(
            "Some database helper functions are still intentionally lightweight, "
            "so certain answers may be simpler than the final production version."
        )

    with st.expander("Why might usage stats look odd?"):
        st.markdown(
            "Usage and cost estimates are approximate and depend on the local pricing configuration."
        )

    st.divider()

    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()


st.title(APP_TITLE)
st.subheader(APP_SUBTITLE)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            st.text(message["content"])
        else:
            st.markdown(message["content"])


if prompt := st.chat_input("Ask about your donor community..."):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()

        try:
            with st.status("Analyzing IASC database...", expanded=True) as status:
                response, usage = get_response(
                    user_message=prompt,
                    conversation_history=st.session_state.messages[:-1],
                    model=selected_model,
                    session_tracker=st.session_state.tracker,
                )
                status.update(label="Analysis Complete!", state="complete", expanded=False)

            response_placeholder.text(response)

            try:
                st.caption(
                    f"Model: {selected_model} | "
                    f"Prompt tokens: {getattr(usage, 'prompt_token_count', 0)} | "
                    f"Output tokens: {getattr(usage, 'candidates_token_count', 0)}"
                )
            except Exception:
                pass

            st.session_state.messages.append({"role": "assistant", "content": response})

        except Exception as e:
            st.error(f"Request failed: {e}")


