import os
import requests
import duckdb
import pandas as pd
import plotly.express as px

from dotenv import load_dotenv
from pathlib import Path
from typing_extensions import TypedDict

from langgraph.graph import START, END, StateGraph

# =====================================================
# LOAD ENV VARIABLES
# =====================================================

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

print("Langresp started loading")

# =====================================================
# ENV VARIABLES
# =====================================================

BASE_URL        = os.getenv("BASE_URL")
DEPLOYMENT      = os.getenv("DEPLOYMENT")
API_VERSION     = os.getenv("API_VERSION")
API_KEY         = os.getenv("GENAI_FARM_API_KEY")
SUBSCRIPTION_ID = os.getenv("SUBSCRIPTION_ID")

print("BASE_URL:", BASE_URL)
print("DEPLOYMENT:", DEPLOYMENT)

# =====================================================
# CSV FILE PATH
# =====================================================

#file_path = "AI Agent demo files/Auto Sales data.csv"
file_path = "AI Agent demo files/IAM.csv"

# =====================================================
# LOAD SAMPLE DATA
# =====================================================

try:
    sample_df = duckdb.query(
        f"SELECT * FROM read_csv_auto('{file_path}') LIMIT 5"
    ).to_df()

    column_names = list(sample_df.columns)

    print("\nAVAILABLE COLUMNS:\n")
    print(column_names)

except Exception as e:
    print("CSV LOAD ERROR:", e)
    column_names = []

# =====================================================
# STATE
# =====================================================

class State(TypedDict):
    question: str
    query:    str
    result:   any
    answer:   str
    code:     str

# =====================================================
# LLM API CALL
# =====================================================

def call_llm(prompt):

    url = (
        f"{BASE_URL}/api/openai/deployments/{DEPLOYMENT}"
        f"/chat/completions?api-version={API_VERSION}"
    )

    headers = {
        "Content-Type": "application/json",
        "genaiplatform-farm-subscription-key": API_KEY,
        "x-genaiplatform-subscription-id": SUBSCRIPTION_ID,
    }

    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)

    if response.status_code != 200:
        print("\nERROR RESPONSE:\n", response.text)

    response.raise_for_status()

    return response.json()["choices"][0]["message"]["content"]

# =====================================================
# STEP 1 – GENERATE SQL QUERY
# =====================================================

def write_query(state: State):

    prompt = f"""
You are an expert DuckDB SQL analyst.

CSV FILE:
{file_path}

AVAILABLE COLUMNS:
{column_names}

USER QUESTION:
{state['question']}

IMPORTANT RULES:
1. Generate ONLY a SQL query — no explanation, no markdown fences.
2. Use DuckDB syntax.
3. Use ONLY available columns listed above.
4. Always query using: read_csv_auto('{file_path}')
5. Add aliases for readability.
6. Use GROUP BY for aggregations.
7. Use ORDER BY where appropriate.
8. Use LIMIT 10 unless the user explicitly asks for more or fewer rows.
9. NEVER invent column names.

EXAMPLE:
SELECT COUNTRY, SUM(SALES) AS TOTAL_SALES
FROM read_csv_auto('{file_path}')
GROUP BY COUNTRY
ORDER BY TOTAL_SALES DESC
"""

    sql_query = call_llm(prompt)
    sql_query = sql_query.replace("```sql", "").replace("```", "").strip()

    print("\nGenerated SQL Query:\n", sql_query)

    return {"query": sql_query}

# =====================================================
# STEP 2 – EXECUTE QUERY
# =====================================================

def execute_query(state: State):

    try:
        df = duckdb.query(state["query"]).to_df()
        print("\nQuery Result:\n", df.head())
        return {"result": df}

    except Exception as e:
        error_msg = f"SQL Error: {str(e)}"
        print(error_msg)
        return {"result": error_msg}

# =====================================================
# STEP 3 – GENERATE BUSINESS INSIGHTS
# =====================================================

def generate_answer(state: State):

    if isinstance(state["result"], str):
        return {"answer": state["result"]}

    prompt = f"""
You are a business analyst.

USER QUESTION:
{state['question']}

DATA:
{state['result'].head(10).to_string()}

Generate concise business insights in bullet points.
"""

    answer = call_llm(prompt)
    return {"answer": answer}

# =====================================================
# STEP 4 – GENERATE CHART CODE
# =====================================================

def write_code_for_chart(state: State):
    """
    Generates a Plotly chart code snippet.
    The code must assign a figure to the variable `fig` — nothing else.
    Actual rendering is done by vizchatbot.py so there is NO st.plotly_chart here.
    """

    if isinstance(state["result"], str):
        return {"code": ""}

    df      = state["result"]
    columns = list(df.columns)

    print("\nCHART DATAFRAME COLUMNS:\n", columns)

    if len(columns) < 2:
        return {"code": ""}

    x_col    = columns[0]
    y_col    = columns[1]
    question = state["question"].lower()

    # ── Auto chart-type detection ──────────────────────────────────────────

    if any(kw in question for kw in ["trend", "monthly", "date", "year", "over time"]):
        code = f"""
fig = px.line(
    df,
    x='{x_col}',
    y='{y_col}',
    markers=True,
    title='{y_col} Trend by {x_col}'
)
fig.update_layout(template='plotly_white', height=500)
"""

    elif any(kw in question for kw in ["pie", "contribution", "share", "distribution", "breakdown"]):
        code = f"""
fig = px.pie(
    df,
    names='{x_col}',
    values='{y_col}',
    title='{y_col} Contribution by {x_col}'
)
fig.update_layout(height=500)
"""

    else:
        # Default: horizontal bar chart — easier to read for top-N lists
        code = f"""
fig = px.bar(
    df,
    x='{y_col}',
    y='{x_col}',
    orientation='h',
    title='{y_col} by {x_col}',
    text_auto=True,
    color='{y_col}',
    color_continuous_scale='Blues'
)
fig.update_layout(
    template='plotly_white',
    height=500,
    yaxis=dict(autorange='reversed')
)
"""

    print("\nGenerated Chart Code:\n", code)
    return {"code": code}

# =====================================================
# LANGGRAPH FLOW
# =====================================================

graph_builder = StateGraph(State)

graph_builder.add_node("write_query",         write_query)
graph_builder.add_node("execute_query",        execute_query)
graph_builder.add_node("generate_answer",      generate_answer)
graph_builder.add_node("write_code_for_chart", write_code_for_chart)

graph_builder.add_edge(START,                  "write_query")
graph_builder.add_edge("write_query",          "execute_query")
graph_builder.add_edge("execute_query",        "generate_answer")
graph_builder.add_edge("generate_answer",      "write_code_for_chart")
graph_builder.add_edge("write_code_for_chart", END)

graph = graph_builder.compile()

# =====================================================
# PUBLIC FUNCTION
# =====================================================

def llm_result(question: str):

    results = []

    for step in graph.stream({"question": question}, stream_mode="updates"):
        print(step)
        results.append(step)

    return results

print("Langresp loaded successfully")