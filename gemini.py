import streamlit as st
import mysql.connector
import pandas as pd
import ollama 
import matplotlib.pyplot as plt
import re 
import io

# --- Page Config ---
st.set_page_config(page_title="AI Data Analyst", page_icon="🤖", layout="wide")

# --- Custom CSS for a Premium Look ---
st.markdown("""
<style>
    /* Dark Theme Overrides */
    .stApp { background-color: #0E1117; color: #E0E0E0; }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #30363D;
    }

    /* Custom Chat Bubbles */
    .stChatMessage {
        background-color: #1C2128 !important;
        border: 1px solid #30363D !important;
        border-radius: 15px !important;
        margin: 10px 0 !important;
    }

    /* Gradient Title */
    .main-title {
        background: linear-gradient(90deg, #A78BFA, #6366F1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 3rem;
        text-align: center;
        margin-bottom: 0px;
    }

    /* Status Pill */
    .status-pill {
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: bold;
        background: #238636;
        color: white;
        display: inline-block;
    }
    
    /* Metrics Styling */
    [data-testid="stMetric"] {
        background-color: #161B22;
        border: 1px solid #30363D;
        padding: 15px;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------- DATABASE LOGIC ----------------

def upload_csv_to_mysql(uploaded_file, cursor, conn):
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

# ---------------- DB CONNECTION ----------------

# Cache connection to prevent flickering on rerun
@st.cache_resource
def get_db_connection():
    return mysql.connector.connect(
        host="localhost", user="root", password="root123", database="company"
    )

conn = get_db_connection()
cursor = conn.cursor()

# ---------------- SIDEBAR ----------------

with st.sidebar:
    st.markdown("## 📂 Data Center")
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"], label_visibility="collapsed")
    
    if uploaded_file:
        if st.session_state.get("uploaded_filename") != uploaded_file.name:
            with st.spinner("Processing..."):
                t_name, p_df = upload_csv_to_mysql(uploaded_file, cursor, conn)
                st.session_state.update({
                    "active_table": t_name,
                    "active_columns": list(p_df.columns),
                    "preview_df": p_df.head(5),
                    "uploaded_filename": uploaded_file.name
                })
        
        st.markdown(f'<div class="status-pill">● Online: {st.session_state["active_table"]}</div>', unsafe_allow_html=True)
        st.markdown("### Preview")
        st.dataframe(st.session_state["preview_df"], use_container_width=True)

    st.markdown("---")
    if st.button("🗑️ Reset Workspace", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ---------------- MAIN UI ----------------

st.markdown('<p class="main-title">AI Data Analyst</p>', unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #8B949E;'>Natural Language Querying for your Databases</p>", unsafe_allow_html=True)

# Sample Questions as clickable tags
st.markdown("### 💡 Suggestions")
cols = st.columns(4)
suggestions = ["Show sales", "Top 5 products", "Total revenue", "Monthly trends"]
for i, q in enumerate(suggestions):
    if cols[i].button(q, key=f"sug_{i}", use_container_width=True):
        st.session_state["prefill"] = q

# Chat Display
chat_container = st.container()
with chat_container:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# Input Logic
user_input = st.chat_input("Ask a question about your data...")
if "prefill" in st.session_state and not user_input:
    user_input = st.session_state.pop("prefill")

# ---------------- ANALYTICS LOGIC ----------------

def get_sql_from_ai(question):
    table = st.session_state.get("active_table", "data")
    cols = ", ".join(st.session_state.get("active_columns", []))
    prompt = f"Table: {table}. Columns: {cols}. User: {question}. Output ONLY valid MySQL. No text."
    response = ollama.chat(model="llama3", messages=[{"role": "user", "content": prompt}])
    return response['message']['content']

def clean_sql(output):
    output = output.replace("```sql", "").replace("```", "").strip()
    match = re.search(r"(SELECT|SHOW|DESCRIBE)\b.*?;?", output, re.I | re.DOTALL)
    return match.group(0) if match else output

if user_input:
    if "active_table" not in st.session_state:
        st.error("Please upload a CSV file first!")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        # 1. SQL Generation
        with st.status("Querying Database...", expanded=False) as status:
            raw_sql = get_sql_from_ai(user_input)
            sql_query = clean_sql(raw_sql)
            st.code(sql_query, language="sql")
            
            cursor.execute(sql_query)
            df = pd.DataFrame(cursor.fetchall(), columns=[c[0] for c in cursor.description])
            st.session_state["last_df"] = df
            status.update(label="Analysis Complete!", state="complete")

        # 2. Results Layout
        if not df.empty:
            tab1, tab2 = st.tabs(["📊 Visualization", "📄 Data Table"])
            
            with tab1:
                # Basic plot logic
                num_cols = df.select_dtypes(include=['number']).columns
                if not num_cols.empty and len(df) > 1:
                    st.line_chart(df.set_index(df.columns[0])[num_cols[0]])
                elif len(df) == 1 and not num_cols.empty:
                    st.metric("Result", f"{df[num_cols[0]].iloc[0]:,.2f}")
                else:
                    st.info("Visual not applicable for this data.")

            with tab2:
                st.dataframe(df, use_container_width=True)
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download CSV", csv, "data.csv", "text/csv")
            
            st.session_state.messages.append({"role": "assistant", "content": f"Found {len(df)} results for your query."})
        else:
            st.warning("No results found.")