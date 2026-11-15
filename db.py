import time

import mysql.connector
import pandas as pd
import streamlit as st

from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, QUERY_TIMEOUT_SECONDS
from security import add_execution_time_hint


@st.cache_resource
def get_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        connection_timeout=QUERY_TIMEOUT_SECONDS,
    )


def run_query(sql: str):
    """Executes an already-validated SELECT and returns (df, elapsed_seconds)."""
    conn = get_connection()
    cursor = conn.cursor()
    hinted_sql = add_execution_time_hint(sql, QUERY_TIMEOUT_SECONDS)

    start = time.time()
    cursor.execute(hinted_sql)
    rows = cursor.fetchall()
    columns = [c[0] for c in cursor.description] if cursor.description else []
    elapsed = time.time() - start
    cursor.close()

    df = pd.DataFrame(rows, columns=columns)
    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col])
        except (ValueError, TypeError):
            pass
    return df, elapsed


def upload_csv_to_mysql(uploaded_file, conn):
    """Reads a CSV and creates + populates a MySQL table automatically."""
    df = pd.read_csv(uploaded_file)
    df.columns = [c.strip().replace(" ", "_").replace("-", "_").lower() for c in df.columns]
    table_name = uploaded_file.name.rsplit(".", 1)[0].replace(" ", "_").lower()

    def sql_type(series):
        if pd.api.types.is_integer_dtype(series):
            return "INT"
        if pd.api.types.is_float_dtype(series):
            return "FLOAT"
        return "VARCHAR(255)"

    col_defs = ", ".join(f"`{c}` {sql_type(df[c])}" for c in df.columns)

    cursor = conn.cursor()
    cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
    cursor.execute(f"CREATE TABLE `{table_name}` ({col_defs})")

    placeholders = ", ".join(["%s"] * len(df.columns))
    values = [tuple(None if pd.isna(v) else v for v in row) for _, row in df.iterrows()]
    cursor.executemany(f"INSERT INTO `{table_name}` VALUES ({placeholders})", values)
    conn.commit()
    cursor.close()
    return table_name, df
