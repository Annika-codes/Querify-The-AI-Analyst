import streamlit as st
import mysql.connector
import pandas as pd
import ollama 
import matplotlib.pyplot as plt
import re 
import csv
import io

#-------------------csv--------------------------------------------

def upload_csv_to_mysql(uploaded_file, cursor, conn):
    """Reads a CSV file and creates + populates a MySQL table automatically."""
    
    # Read the file into a pandas DataFrame
    df = pd.read_csv(uploaded_file)
    
    # Clean column names (remove spaces, special chars)
    df.columns = [col.strip().replace(" ", "_").replace("-", "_").lower() for col in df.columns]
    
    # Use the uploaded file name as table name (without .csv)
    table_name = uploaded_file.name.replace(".csv", "").replace(" ", "_").lower()
    
    # --- Auto-detect column types ---
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

st.title("🤖")

# ---------------- DATABASE CONNECTION ----------------

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root123",   
    database="company"
)
cursor = conn.cursor()

# ------------CSV UPLOAD-------------------------------

st.sidebar.header("📂 Upload Your Dataset")
uploaded_file = st.sidebar.file_uploader("Upload a CSV file", type=["csv"])

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

# ---------------- CHAT MEMORY -------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

# show old messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# input box
user_input = st.chat_input("Ask anything about your data...")

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
        numeric_cols = df.select_dtypes(include=['number']).columns
        if len(numeric_cols) == 0:
            return

        # ✅ Single value result (e.g. total sales) — show as metric
        if len(df) == 1 and len(df.columns) == 1:
            st.metric(label=numeric_cols[0], value=df[numeric_cols[0]].iloc[0])
            return

        # ✅ Single row but multiple columns — horizontal bar
        if len(df) == 1:
            st.bar_chart(df[numeric_cols])
            return

        # Normal case — needs a text column for x-axis
        text_cols = df.select_dtypes(exclude=['number']).columns
        if len(text_cols) == 0:
            st.bar_chart(df[numeric_cols])
            return

        x_col = text_cols[0]
        y_col = numeric_cols[0]

        fig, ax = plt.subplots()
        ax.bar(df[x_col].astype(str), df[y_col])
        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        ax.set_title("Analysis")
        st.pyplot(fig)

    except Exception as e:
        st.write("Chart error:", e)

# ---------------- MAIN LOGIC ----------------

if "active_table" not in st.session_state:
    st.warning("⬅️ Please upload a CSV file from the sidebar first!")
    st.stop() 
    
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    try:
        intent = get_intent(user_input)

        with st.chat_message("assistant"):

            # ---------------- DATA MODE ----------------
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
                    df = pd.DataFrame(list(result), columns=columns)

                    for col in df.columns:
                        try:
                            df[col] = pd.to_numeric(df[col])
                        except:
                            pass
                    
                    # save data for later explanation
                    st.session_state["last_df"] = df

                    st.write("Result:")
                    st.dataframe(df)
            
                 # -------- SMART CHART --------
                    plot_chart(df)

            # ---------------- EXPLAIN MODE ----------------
            else:
                df = st.session_state.get("last_df", None)

                if df is not None:
                    explanation = explain_result(user_input, df)
                    st.subheader("Explanation")
                    st.write(explanation)
                else:
                    st.write("No data available yet. Ask a data question first.")

    except Exception as e:
        st.error("Something went wrong")
        st.write(e)
