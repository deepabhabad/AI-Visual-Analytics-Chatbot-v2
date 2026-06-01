import streamlit as st
import time
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import pandas as pd

from Langresp import llm_result

# =====================================================
# STREAM RESPONSE EFFECT
# =====================================================

def chat_stream(text):
    for char in text:
        yield char
        time.sleep(0.01)

# =====================================================
# SAVE FEEDBACK
# =====================================================

def save_feedback(index):
    st.session_state.history[index]["feedback"] = st.session_state[f"feedback_{index}"]

# =====================================================
# RENDER CHART HELPER
# =====================================================

def render_chart(chart_code, result_df):
    """Execute chart code and display the resulting figure."""
    if not chart_code or result_df is None:
        return

    try:
        import plotly.express as px

        chart_code_clean = chart_code.replace("```python", "").replace("```", "").strip()

        local_vars = {
            "st": st,
            "go": go,
            "plt": plt,
            "pd": pd,
            "px": px,
            "df": result_df
        }

        exec(chart_code_clean, {}, local_vars)

        # KEY FIX: after exec, grab `fig` from local_vars and render it
        if "fig" in local_vars:
            fig = local_vars["fig"]
            fig.update_layout(template="plotly_white", height=500)
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Chart rendering error: {e}")

# =====================================================
# SESSION STATE
# =====================================================

if "history" not in st.session_state:
    st.session_state.history = []

if "charts" not in st.session_state:
    st.session_state.charts = []

if "dataframes" not in st.session_state:
    st.session_state.dataframes = []

# =====================================================
# DISPLAY OLD CHAT HISTORY
# =====================================================

for i, message in enumerate(st.session_state.history):

    with st.chat_message(message["role"]):

        st.write(message["content"])

        if message["role"] == "assistant":

            # Re-render chart for this turn if available
            chart_code = st.session_state.charts[i] if i < len(st.session_state.charts) else ""
            result_df  = st.session_state.dataframes[i] if i < len(st.session_state.dataframes) else None

            render_chart(chart_code, result_df)

            # Feedback widget
            feedback = message.get("feedback", None)
            st.session_state[f"feedback_{i}"] = feedback

            st.feedback(
                "thumbs",
                key=f"feedback_{i}",
                disabled=feedback is not None,
                on_change=save_feedback,
                args=[i],
            )

# =====================================================
# INITIAL WELCOME MESSAGE
# =====================================================

if not st.session_state.history:

    init_msg = "Hello there, how are you?\n\nHow can I help you today?"

    st.session_state.history.append({"role": "assistant", "content": init_msg})
    st.session_state.charts.append("")
    st.session_state.dataframes.append(None)

    with st.chat_message("assistant"):
        st.write(init_msg)

# =====================================================
# HANDLE USER INPUT
# =====================================================

if prompt := st.chat_input("Ask your question here..."):

    # Store user message
    st.session_state.history.append({"role": "user", "content": prompt})
    st.session_state.charts.append("")
    st.session_state.dataframes.append(None)

    with st.chat_message("user"):
        st.write(prompt)

    # Call LLM
    try:
        result = llm_result(prompt)

        answer     = "Sorry, I could not generate a response."
        chart_code = ""
        result_df  = None

        # Extract results from graph steps
        for step in result:
            if "generate_answer" in step:
                answer = step["generate_answer"]["answer"]
            if "write_code_for_chart" in step:
                chart_code = step["write_code_for_chart"]["code"]
            if "execute_query" in step:
                result_df = step["execute_query"]["result"]

        # Store assistant response
        st.session_state.history.append({"role": "assistant", "content": answer})
        st.session_state.charts.append(chart_code)
        st.session_state.dataframes.append(result_df)

        # Display response
        with st.chat_message("assistant"):

            st.write_stream(chat_stream(answer))

            # Render the chart right after the streamed text
            render_chart(chart_code, result_df)

            # Feedback
            i = len(st.session_state.history) - 1
            st.session_state[f"feedback_{i}"] = None

            st.feedback(
                "thumbs",
                key=f"feedback_{i}",
                disabled=False,
                on_change=save_feedback,
                args=[i],
            )

    except Exception as e:
        st.error(f"Application Error: {e}")