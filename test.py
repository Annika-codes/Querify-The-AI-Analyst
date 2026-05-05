import streamlit as st
import mysql.connector
import pandas as pd
import ollama 
import matplotlib.pyplot as plt
import re 
import csv
import io
import json 

#-------------------csv--------------------------------------------

def upload_csv_to_mysql(uploaded_file, cursor, conn):
    """Reads a CSV file and creates + populates a MySQL table automatically."""
    
    # Read the file into a pandas DataFrame
    df = pd.read_csv(uploaded_file)
    
    # Clean column names (remove spaces, special chars)
    df.columns = [col.strip().replace(" ", "_").replace("-", "_").lower() for col in df.columns]
    
    # Use the uploaded file name as table name (without .csv)
    table_name = uploaded_file.name.replace(".csv", "").replace(" ", "_").lower()
    
    # --- Auto-detect column types -------
    def get_sql_type(series):
        if pd.api.types.is_integer_dtype(series):
            return "INT"
        elif pd.api.types.is_float_dtype(series):
            return "FLOAT"
        else:
            return "VARCHAR(255)"
    
    # --- Build CREATE TABLE statement ---
    col_definitions = ", ".join(
        f"`{col}` {get_sql_type(df[col])}" for col in df.columns
    )
    create_query = f"DROP TABLE IF EXISTS `{table_name}`; CREATE TABLE `{table_name}` ({col_definitions});"
    
    # Execute table creation
    cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
    cursor.execute(f"CREATE TABLE `{table_name}` ({col_definitions})")
    
    # --- Insert rows ---
    for _, row in df.iterrows():
        values = tuple(None if pd.isna(v) else v for v in row)
        placeholders = ", ".join(["%s"] * len(row))
        insert_query = f"INSERT INTO `{table_name}` VALUES ({placeholders})"
        cursor.execute(insert_query, values)
    
    conn.commit()
    return table_name, df

#------TITLE-------------------------------------------

st.markdown("""
    <h1 style='text-align: center; color: #a78bfa;'>🤖 AI Data Analyst</h1>
    <hr style='border: 1px solid #2e2e3e;'>
""", unsafe_allow_html=True)

#---------------------CSS---------------------------
st.markdown("""
<style>
    /* Main background */
    .stApp { background-color: #0f1117; }
    
    /* Chat messages */
    .stChatMessage { 
        border-radius: 12px; 
        padding: 10px;
        margin-bottom: 8px;
    }
    
    /* Stop messages fading */
    .stChatMessage {
    opacity: 1 !important;
    transition: none !important;
    }

    /* Scrollable chat area */
    [data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid #2e2e3e !important;
    border-radius: 12px !important;
    padding: 10px !important;
    background-color: #0f1117 !important;
    }
                   
    /* User bubble */
    [data-testid="stChatMessageContent"] {
        background-color: #1e2130;
        border-radius: 10px;
        padding: 8px 12px;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #161822;
        border-right: 1px solid #2e2e3e;
    }

    /* Buttons */
    .stButton > button {
        background-color: #2e2e4e;
        color: white;
        border: 1px solid #4e4e8e;
        border-radius: 8px;
        width: 100%;
        margin-bottom: 6px;
        transition: 0.2s;
    }
    .stButton > button:hover {
        background-color: #4e4e9e;
        border-color: #8888ff;
    }

    /* Dataframe */
    .stDataFrame { border-radius: 10px; overflow: hidden; }

    /* Title */
    h1 { color: #a78bfa !important; }
</style>
""", unsafe_allow_html=True)

# ---------------- DATABASE CONNECTION ----------------

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root123",   
    database="company"
)
cursor = conn.cursor()

# ------------CSV UPLOAD-------------------------------

st.sidebar.markdown("""
    <h2 style='color: #a78bfa;'>📂 Your Dataset</h2>
    <p style='color: #888; font-size: 13px;'>Upload a CSV to get started</p>
""", unsafe_allow_html=True)

uploaded_file = st.sidebar.file_uploader("", type=["csv"])

if uploaded_file is not None:
    # ✅ Only re-upload if it's a NEW file
    if st.session_state.get("uploaded_filename") != uploaded_file.name:
        with st.spinner("Uploading and creating table..."):
            try:
                table_name, preview_df = upload_csv_to_mysql(uploaded_file, cursor, conn)
                st.session_state["active_table"] = table_name
                st.session_state["active_columns"] = list(preview_df.columns)
                st.session_state["preview_df"] = preview_df.reset_index(drop=True)
                st.session_state["uploaded_filename"] = uploaded_file.name  # ✅ track filename
                st.sidebar.success(f"✅ Table `{table_name}` created with {len(preview_df)} rows!")
            except Exception as e:
                st.sidebar.error(f"❌ Upload failed: {e}")
    else:
        # Already uploaded — just show the saved preview
        st.sidebar.success(f"✅ Table `{st.session_state['active_table']}` ready!")

    # Always show the preview from session
    if "preview_df" in st.session_state:
        st.sidebar.write("**Preview:**")
        st.sidebar.dataframe(st.session_state["preview_df"])
    st.sidebar.markdown("---")
    if st.sidebar.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.session_state.pop("last_df", None)
        st.rerun()    

# ---------------- CHAT MEMORY -------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

# show old messages
chat_container = st.container()
with chat_container:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

# prefilled question from button click
user_input = st.chat_input("Ask anything about your data...")

if "prefill" in st.session_state and not user_input:
    user_input = st.session_state.pop("prefill")

# ---------------- AI FUNCTION ----------------------------

def clean_sql(output):
    output = output.replace("```sql", "").replace("```", "").strip()
    
    match = re.search(
        r"(SELECT|INSERT|UPDATE|DELETE|SHOW|DESCRIBE)\b.*?;",
        output,
        re.IGNORECASE | re.DOTALL
    )
    if match:
        return match.group(0).strip()
    
    return output.strip()

def get_sql_from_ai(question):
    table_name = st.session_state.get("active_table", "sales")
    columns = st.session_state.get("active_columns", [])
    column_info = ", ".join(columns) if columns else "unknown"

    prompt = f"""
    You are a MySQL expert. Output ONLY a valid MySQL query.
    No explanation. No steps. No comments. Just SQL.
    - Use GROUP BY when using aggregate functions like SUM, COUNT, AVG
    - Never use aggregate functions directly in ORDER BY — use the alias instead
    - Example: SELECT product, SUM(amount) AS total FROM sales GROUP BY product ORDER BY total DESC

    Table: `{table_name}`
    Columns: {column_info}

    Question: {question}
    SQL:
    """

    response = ollama.chat(
        model="llama3",
        messages=[{"role": "user", "content": prompt}]
    )
    return response['message']['content']

#---------Ai explaination ---------

def explain_result(question, df):
    try:
        explanation_prompt = f"""
        The user asked: {question}

        The result data is:
        {df.to_string()}

        Explain this result in simple English like a data analyst.
        """

        response = ollama.chat(
            model="llama3",
            messages=[{"role": "user", "content": explanation_prompt}]
        )

        return response['message']['content']

    except Exception as e:
        return "Could not generate explanation."
    
 #--------underatnd qs------------------------------------------------------------

def get_intent(question):
    prompt = f"""
    Classify the user's intent.
    If the user is asking for data (totals, list, counts, tables, sales), return: DATA
    If the user is asking for explanation, reasoning, insights, or discussion, return: EXPLAIN
    Only return one word: DATA or EXPLAIN

    Question: {question}
    """

    response = ollama.chat(
        model="llama3",
        messages=[{"role": "user", "content": prompt}]
    )
    return response['message']['content'].strip().upper()

#----smart chart-------------------------------------------------------------------

def plot_chart(df):
    try:
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        text_cols = df.select_dtypes(exclude=['number']).columns.tolist()

        if len(numeric_cols) == 0:
            return

        # ✅ Single value — show as metric card
        if len(df) == 1 and len(df.columns) == 1:
            st.metric(label=numeric_cols[0], value=f"{df[numeric_cols[0]].iloc[0]:,.0f}")
            return

        # ✅ Date column detected — Line chart
        date_col = None
        for col in text_cols:
            try:
                df[col] = pd.to_datetime(df[col])
                date_col = col
                break
            except:
                pass

        if date_col:
            y_col = numeric_cols[0]
            fig, ax = plt.subplots()
            ax.plot(df[date_col], df[y_col], marker='o', color='#a78bfa')
            ax.set_xlabel(date_col)
            ax.set_ylabel(y_col)
            ax.set_title(f"{y_col} over time")
            plt.xticks(rotation=45)
            plt.tight_layout()
            st.pyplot(fig)
            return

        # ✅ Few categories — Pie chart
        if len(text_cols) > 0 and len(df) <= 6:
            x_col = text_cols[0]
            y_col = numeric_cols[0]
            fig, ax = plt.subplots()
            ax.pie(
                df[y_col],
                labels=df[x_col],
                autopct='%1.1f%%',
                colors=['#a78bfa','#7c3aed','#6d28d9','#4c1d95','#8b5cf6','#c4b5fd']
            )
            ax.set_title(f"{y_col} distribution")
            st.pyplot(fig)
            return

        # ✅ Default — Bar chart
        if len(text_cols) > 0:
            x_col = text_cols[0]
            y_col = numeric_cols[0]
            fig, ax = plt.subplots()
            ax.bar(df[x_col].astype(str), df[y_col], color='#a78bfa')
            ax.set_xlabel(x_col)
            ax.set_ylabel(y_col)
            ax.set_title(f"{y_col} by {x_col}")
            plt.xticks(rotation=45)
            plt.tight_layout()
            st.pyplot(fig)
            return

    except Exception as e:
        st.write("Chart error:", e)

# ---------------- AI SUGGESTIONS ----------------

def generate_suggestions():
    table_name = st.session_state.get("active_table", "")
    columns = st.session_state.get("active_columns", [])
    past_questions = [
        msg["content"] for msg in st.session_state.get("messages", [])
        if msg["role"] == "user"
    ]

    if not table_name or not columns:
        return []

    column_info = ", ".join(columns)
    history_info = "\n".join(f"- {q}" for q in past_questions[-5:]) if past_questions else "None yet"

    prompt = f"""
    You are a data analyst assistant. Suggest exactly 4 short, relevant questions a user might ask
    about this dataset. Make them specific to the columns available.
    If past questions exist, suggest follow-up or related questions.

    Table: `{table_name}`
    Columns: {column_info}

    Past questions asked:
    {history_info}

    Return ONLY a JSON array of 4 question strings. No explanation. No extra text.
    Example: ["Question 1", "Question 2", "Question 3", "Question 4"]
    """

    try:
        response = ollama.chat(
            model="llama3",
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response['message']['content'].strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        suggestions = json.loads(raw)
        return suggestions if isinstance(suggestions, list) else []
    except Exception:
        return []

# ---------------- MAIN LOGIC ------------------------------------------------------

if "active_table" not in st.session_state:
    st.warning("⬅️ Please upload a CSV file from the sidebar first!")
    st.stop() 

msg_count = len(st.session_state.get("messages", []))
last_regen = st.session_state.get("suggestions_regen_at", -1)

if st.session_state.get("suggestions") is None or last_regen != msg_count:
    with st.spinner("Generating suggestions u can ask..."):
        st.session_state["suggestions"] = generate_suggestions()
        st.session_state["suggestions_regen_at"] = msg_count

suggestions = st.session_state.get("suggestions", [])
if suggestions:
    st.markdown("#### 💡 Try asking:")
    cols = st.columns(2)
    for i, q in enumerate(suggestions):
        with cols[i % 2]:
            if st.button(q, key=f"suggestion_{i}_{msg_count}"):
                st.session_state["prefill"] = q

with chat_container:
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        try:
            intent = get_intent(user_input)
            with st.chat_message("assistant"):
                if intent == "DATA":
                    with st.spinner("Analyzing..."):
                        raw_sql = get_sql_from_ai(user_input)
                        sql_query = clean_sql(raw_sql)
                        st.markdown("**Generated SQL:**")
                        st.code(sql_query, language='sql')
                        cursor.execute(sql_query)
                        result = cursor.fetchall()
                        if not result:
                            st.warning("No data returned. Try a different question.")
                            st.stop()
                        columns = [col[0] for col in cursor.description]
                        df = pd.DataFrame(list(result), columns=columns)
                        for col in df.columns:
                            try:
                                df[col] = pd.to_numeric(df[col])
                            except:
                                pass
                        st.session_state["last_df"] = df
                        st.markdown(f"<p style='color: #888; font-size: 13px;'>Showing {len(df)} row(s)</p>", unsafe_allow_html=True)
                        st.dataframe(df)
                        csv_data = df.to_csv(index=False).encode("utf-8")
                        st.download_button(
                            label="⬇️ Download Result as CSV",
                            data=csv_data,
                            file_name="query_result.csv",
                            mime="text/csv"
                        )
                        plot_chart(df)
                        st.session_state.messages.append({"role": "assistant", "content": f"Here are the results for: *{user_input}*"})
                else:
                    df = st.session_state.get("last_df", None)
                    if df is not None:
                        explanation = explain_result(user_input, df)
                        st.subheader("Explanation")
                        st.write(explanation)
                        st.session_state.messages.append({"role": "assistant", "content": explanation})
                    else:
                        st.write("No data available yet. Ask a data question first.")
        except Exception as e:
            st.error("Something went wrong")
            st.write(e)