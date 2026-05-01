import streamlit as st
import mysql.connector
import pandas as pd
import ollama 
import matplotlib.pyplot as plt
import re 
import uuid

# ---------------- DATABASE SETUP ----------------

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root123",   
        database="company"
    )

conn = get_db_connection()
cursor = conn.cursor()

# Create table for persistent chat history if it doesn't exist
cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        session_id VARCHAR(255),
        role VARCHAR(50),
        content TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()

# ---------------- HELPER FUNCTIONS ----------------

def save_message(role, content):
    session_id = st.session_state.get("session_id", "default")
    query = "INSERT INTO chat_history (session_id, role, content) VALUES (%s, %s, %s)"
    cursor.execute(query, (session_id, role, content))
    conn.commit()

def load_history():
    session_id = st.session_state.get("session_id", "default")
    cursor.execute("SELECT role, content FROM chat_history WHERE session_id = %s ORDER BY timestamp ASC", (session_id,))
    return [{"role": row[0], "content": row[1]} for row in cursor.fetchall()]

def upload_csv_to_mysql(uploaded_file):
    df = pd.read_csv(uploaded_file)
    df.columns = [col.strip().replace(" ", "_").replace("-", "_").lower() for col in df.columns]
    table_name = uploaded_file.name.replace(".csv", "").replace(" ", "_").lower()
    
    def get_sql_type(series):
        if pd.api.types.is_integer_dtype(series): return "INT"
        elif pd.api.types.is_float_dtype(series): return "FLOAT"
        else: return "VARCHAR(255)"
    
    col_definitions = ", ".join(f"`{col}` {get_sql_type(df[col])}" for col in df.columns)
    cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
    cursor.execute(f"CREATE TABLE `{table_name}` ({col_definitions})")
    
    for _, row in df.iterrows():
        values = tuple(None if pd.isna(v) else v for v in row)
        placeholders = ", ".join(["%s"] * len(row))
        cursor.execute(f"INSERT INTO `{table_name}` VALUES ({placeholders})", values)
    
    conn.commit()
    return table_name, df

def get_dynamic_suggestions(tables_dict):
    """Generates initial questions based on uploaded table columns."""
    all_context = ""
    for t, cols in tables_dict.items():
        all_context += f"Table {t} has columns: {', '.join(cols)}. "
    
    prompt = f"Based on these tables: {all_context}. Generate 4 short analytical questions user might ask. Return only the questions separated by newlines."
    response = ollama.chat(model="llama3", messages=[{"role": "user", "content": prompt}])
    return response['message']['content'].strip().split('\n')

def get_follow_up_suggestions(last_query, df_sample):
    """Generates follow-up questions based on the last result."""
    prompt = f"The user just asked: '{last_query}'. The result had columns: {list(df_sample.columns)}. Suggest 3 short follow-up questions. Only return the questions."
    response = ollama.chat(model="llama3", messages=[{"role": "user", "content": prompt}])
    return response['message']['content'].strip().split('\n')

# ---------------- SESSION STATE ----------------

if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())
if "tables" not in st.session_state:
    st.session_state["tables"] = {} # Store table_name: columns
if "messages" not in st.session_state:
    st.session_state.messages = load_history()

# ---------------- UI & SIDEBAR ----------------

st.set_page_config(page_title="AI Data Analyst", layout="wide")
st.markdown("""
<style>
    .stApp { background-color: #0f1117; color: white; }
    [data-testid="stSidebar"] { background-color: #161822; }
    .suggestion-btn { margin: 5px; }
</style>
""", unsafe_allow_html=True)

st.sidebar.title("📂 Multi-Table Manager")
uploaded_files = st.sidebar.file_uploader("Upload CSVs", type=["csv"], accept_multiple_files=True)

if uploaded_files:
    for uploaded_file in uploaded_files:
        if uploaded_file.name not in st.session_state.get("uploaded_filenames", []):
            with st.spinner(f"Processing {uploaded_file.name}..."):
                t_name, df = upload_csv_to_mysql(uploaded_file)
                st.session_state["tables"][t_name] = list(df.columns)
                if "uploaded_filenames" not in st.session_state: st.session_state["uploaded_filenames"] = []
                st.session_state["uploaded_filenames"].append(uploaded_file.name)
    st.sidebar.success(f"Tables loaded: {', '.join(st.session_state['tables'].keys())}")

if st.sidebar.button("🗑️ Clear History"):
    cursor.execute("DELETE FROM chat_history WHERE session_id = %s", (st.session_state.session_id,))
    conn.commit()
    st.session_state.messages = []
    st.rerun()

# ---------------- MAIN CHAT ----------------

st.title("🤖 AI Data Analyst")

# Show dynamic suggestions ONLY after upload
if st.session_state["tables"]:
    if "dynamic_qs" not in st.session_state:
        st.session_state["dynamic_qs"] = get_dynamic_suggestions(st.session_state["tables"])
    
    st.markdown("#### 💡 Suggested for your data:")
    cols = st.columns(2)
    for i, q in enumerate(st.session_state["dynamic_qs"][:4]):
        if cols[i%2].button(q, key=f"sug_{i}"):
            st.session_state["prefill"] = q
else:
    st.info("Please upload one or more CSV files to start analyzing.")

# Display Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_input = st.chat_input("Ask about your data...")
if "prefill" in st.session_state and not user_input:
    user_input = st.session_state.pop("prefill")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    save_message("user", user_input)
    with st.chat_message("user"):
        st.write(user_input)

    # Contextual Logic
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            # Construct Schema Context for Multi-Table Joins
            schema_context = "\n".join([f"Table `{t}`: {', '.join(c)}" for t, c in st.session_state["tables"].items()])
            
            prompt = f"""
            You are a MySQL expert. Use the following schema:
            {schema_context}
            Output ONLY valid MySQL. If multiple tables are needed, use JOINs.
            Question: {user_input}
            SQL:"""
            
            sql_res = ollama.chat(model="llama3", messages=[{"role": "user", "content": prompt}])
            sql_query = sql_res['message']['content'].replace("```sql", "").replace("```", "").strip()
            
            try:
                st.code(sql_query, language="sql")
                cursor.execute(sql_query)
                df = pd.DataFrame(cursor.fetchall(), columns=[c[0] for c in cursor.description])
                st.dataframe(df)
                st.session_state["last_df"] = df
                
                # Explanation
                explain_prompt = f"Explain this data briefly: {df.head(5).to_string()}"
                explanation = ollama.chat(model="llama3", messages=[{"role": "user", "content": explain_prompt}])['message']['content']
                st.write(explanation)
                
                save_message("assistant", f"SQL Result for: {user_input}\n{explanation}")

                # Follow-up Questions
                st.markdown("---")
                st.markdown("##### 🔍 Follow-up Questions:")
                follow_ups = get_follow_up_suggestions(user_input, df)
                f_cols = st.columns(3)
                for i, fq in enumerate(follow_ups[:3]):
                    if f_cols[i].button(fq, key=f"follow_{i}"):
                        st.session_state["prefill"] = fq
                        st.rerun()

            except Exception as e:
                st.error(f"Execution Error: {e}")