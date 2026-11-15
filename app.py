from datetime import datetime

import streamlit as st

import audit
import llm
from auth import require_login
from charts import plot_chart
from config import ADMIN_USERNAMES, MAX_ROWS_RETURNED
from db import get_connection, run_query, upload_csv_to_mysql
from security import UnsafeSQLError, validate_and_limit
from theme import apply_theme, column_type_dot

st.set_page_config(page_title="Querify", layout="wide")
apply_theme()
require_login()

current_user = st.session_state.get("current_user", "unknown")
is_admin = current_user in ADMIN_USERNAMES

st.markdown(
    "<h1 style='text-align:center;'>Querify</h1><hr style='border:1px solid #2A3134;'>",
    unsafe_allow_html=True,
)

conn = get_connection()

# ---------------- SIDEBAR: datasets --------------------------------

st.session_state.setdefault("tables", {})  # table_name -> list[columns]

st.sidebar.markdown("### Your datasets")
uploaded_file = st.sidebar.file_uploader("Upload CSV", type=["csv"], label_visibility="collapsed")

if uploaded_file is not None and uploaded_file.name not in st.session_state.get("uploaded_names", set()):
    with st.spinner("Uploading and creating table..."):
        try:
            table_name, preview_df = upload_csv_to_mysql(uploaded_file, conn)
            st.session_state["tables"][table_name] = list(preview_df.columns)
            st.session_state.setdefault("uploaded_names", set()).add(uploaded_file.name)
            st.session_state["active_table"] = table_name
            st.sidebar.success(f"Table `{table_name}` ready — {len(preview_df)} rows.")
        except Exception as e:
            st.sidebar.error(f"Upload failed: {e}")

if st.session_state["tables"]:
    table_names = list(st.session_state["tables"].keys())
    active = st.sidebar.selectbox(
        "Active dataset",
        table_names,
        index=table_names.index(st.session_state.get("active_table", table_names[0])),
    )
    st.session_state["active_table"] = active
    st.sidebar.caption(", ".join(st.session_state["tables"][active]))

    if st.sidebar.button("Clear chat"):
        st.session_state["messages"] = []
        st.session_state.pop("last_df", None)
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption(f"Signed in as **{current_user}**")

# ---------------- SIDEBAR: admin panel -----------------------------

if is_admin:
    with st.sidebar.expander("Admin: recent activity"):
        logs = audit.get_recent_logs(20)
        for ts, user, question, sql_query, row_count, status in logs:
            when = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
            badge = "ok" if status == "success" else "blocked"
            st.caption(f"`{when}` **{user}** · {badge} · {row_count if row_count is not None else '-'} rows")
            st.text(question)

# ---------------- MAIN: chat ----------------------------------------

if "active_table" not in st.session_state:
    st.warning("Upload a CSV from the sidebar to get started.")
    st.stop()

st.session_state.setdefault("messages", [])

chat_container = st.container()
with chat_container:
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if "df" in msg:
                with st.expander("View result"):
                    if "sql" in msg:
                        st.code(msg["sql"], language="sql")
                    st.dataframe(msg["df"])
                    st.download_button(
                        "Download CSV",
                        msg["df"].to_csv(index=False).encode("utf-8"),
                        file_name="result.csv",
                        mime="text/csv",
                        key=f"dl_{st.session_state['messages'].index(msg)}",
                    )
                    plot_chart(msg["df"])

user_input = st.chat_input("Ask anything about your data...")
if "prefill" in st.session_state and not user_input:
    user_input = st.session_state.pop("prefill")
if user_input:
    st.session_state.pop("suggestions", None)

# ---------------- Suggestions ----------------------------------------

active_table = st.session_state["active_table"]
active_columns = st.session_state["tables"][active_table]
msg_count = len(st.session_state["messages"])

if st.session_state.get("suggestions") is None or st.session_state.get("suggestions_regen_at") != msg_count:
    with st.spinner("Generating suggestions..."):
        past_qs = [m["content"] for m in st.session_state["messages"] if m["role"] == "user"]
        st.session_state["suggestions"] = llm.generate_suggestions(active_table, active_columns, past_qs)
        st.session_state["suggestions_regen_at"] = msg_count

suggestions = st.session_state.get("suggestions", [])
if suggestions:
    st.markdown("#### Try asking")
    cols = st.columns(2)
    for i, q in enumerate(suggestions):
        with cols[i % 2]:
            if st.button(q, key=f"suggestion_{i}_{msg_count}"):
                st.session_state["prefill"] = q

# ---------------- Main turn handling ----------------------------------

with chat_container:
    if user_input:
        st.session_state["messages"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant"):
            try:
                intent = llm.get_intent(user_input)

                if intent == "DATA":
                    with st.spinner("Analyzing..."):
                        raw_sql = llm.get_sql_from_ai(user_input, active_table, active_columns)

                        try:
                            safe_sql = validate_and_limit(raw_sql, MAX_ROWS_RETURNED)
                        except UnsafeSQLError as e:
                            st.error(f"Blocked an unsafe query: {e}")
                            audit.log_query(current_user, user_input, raw_sql, None, "blocked")
                            st.stop()

                        st.markdown("**Generated SQL**")
                        st.code(safe_sql, language="sql")

                        df, elapsed = run_query(safe_sql)
                        audit.log_query(current_user, user_input, safe_sql, len(df), "success")

                        if df.empty:
                            st.warning("No data returned. Try a different question.")
                            st.stop()

                        st.session_state["last_df"] = df
                        st.caption(f"{len(df)} row(s) · {elapsed:.2f}s")

                        header_html = " ".join(
                            column_type_dot("numeric" if df[c].dtype.kind in "if" else "categorical") + c
                            for c in df.columns
                        )
                        st.markdown(header_html, unsafe_allow_html=True)
                        st.dataframe(df)
                        st.download_button(
                            "Download result as CSV",
                            df.to_csv(index=False).encode("utf-8"),
                            file_name="query_result.csv",
                            mime="text/csv",
                        )

                        st.session_state["messages"].append({
                            "role": "assistant",
                            "content": f"Here are the results for: *{user_input}*",
                            "df": df,
                            "sql": safe_sql,
                        })
                        st.rerun()

                else:
                    df = st.session_state.get("last_df")
                    if df is not None:
                        explanation = llm.explain_result(user_input, df)
                        st.subheader("Explanation")
                        st.write(explanation)
                        st.session_state["messages"].append({"role": "assistant", "content": explanation})
                        audit.log_query(current_user, user_input, None, len(df), "explain")
                        st.rerun()
                    else:
                        st.write("No data available yet — ask a data question first.")

            except Exception as e:
                st.error("Something went wrong.")
                st.write(e)
                audit.log_query(current_user, user_input, None, None, "error")
