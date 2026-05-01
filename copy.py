import streamlit as st
import mysql.connector
import pandas as pd
import subprocess

st.title("AI Data Analyst 🤖")

# connect to MySQL
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root123",  # your password
    database="company"
)

cursor = conn.cursor()

# user input (NOW ENGLISH)
user_input = st.text_input("Ask your question:")

def get_sql_from_ai(question):
    prompt = f"""
Convert the following natural language question into a valid MySQL query.

Database has:
Table: sales
Columns: id, product, amount, date

Rules:
- Use correct MySQL syntax
- If asking for all tables, use: SHOW TABLES;
- Only return SQL query (no explanation)

Question: {question}
"""

    result = subprocess.run(
        ["ollama", "run", "llama3"],
        input=prompt,
        text=True,
        capture_output=True
    )

    return result.stdout.strip()

if user_input:
    try:
        sql_query = get_sql_from_ai(user_input)
        st.write("Generated SQL:", sql_query)

        cursor.execute(sql_query)
        result = cursor.fetchall()

        columns = [col[0] for col in cursor.description]
        df = pd.DataFrame(result, columns=columns)

        st.dataframe(df)

    except Exception as e:
        st.error("Something went wrong. Try rephrasing your question.")
        st.write("Error details:", e)
        