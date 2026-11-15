import json
import re

import ollama

from config import OLLAMA_MODEL, SEMANTIC_LAYER


def _semantic_layer_block() -> str:
    if not SEMANTIC_LAYER:
        return ""
    lines = "\n".join(f"- {term}: {definition}" for term, definition in SEMANTIC_LAYER.items())
    return f"\nBusiness term definitions — use these exactly, don't reinterpret:\n{lines}\n"


def clean_sql(output: str) -> str:
    output = output.replace("```sql", "").replace("```", "").strip()
    match = re.search(r"(SELECT)\b.*?;", output, re.IGNORECASE | re.DOTALL)
    return match.group(0).strip() if match else output.strip()


def get_sql_from_ai(question: str, table_name: str, columns: list[str]) -> str:
    column_info = ", ".join(columns) if columns else "unknown"
    prompt = f"""
    You are a MySQL expert. Output ONLY a single, valid, read-only MySQL SELECT
    query. No explanation, no comments, no DDL or write statements.
    - Use GROUP BY when using aggregate functions like SUM, COUNT, AVG
    - Never use aggregate functions directly in ORDER BY — use the alias instead
    - Whatever expression you use in SELECT, use the exact same expression in GROUP BY
    {_semantic_layer_block()}
    Table: `{table_name}`
    Columns: {column_info}

    Question: {question}
    SQL:
    """
    response = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": prompt}])
    return clean_sql(response["message"]["content"])


def get_intent(question: str) -> str:
    prompt = f"""
    Classify the user's intent. Return exactly one word.
    DATA - asking for totals, lists, counts, or tables
    EXPLAIN - asking for reasoning, insight, or discussion of a prior result
    Question: {question}
    """
    response = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": prompt}])
    return response["message"]["content"].strip().upper()


def explain_result(question: str, df) -> str:
    prompt = f"""
    The user asked: {question}
    Result data:
    {df.to_string()}

    Explain this result in plain English like a data analyst. Base the
    explanation only on the data shown above — don't introduce numbers
    that aren't in it.
    """
    response = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": prompt}])
    return response["message"]["content"]


def generate_suggestions(table_name: str, columns: list[str], past_questions: list[str]) -> list[str]:
    column_info = ", ".join(columns)
    history = "\n".join(f"- {q}" for q in past_questions[-5:]) or "None yet"
    prompt = f"""
    Suggest exactly 4 short questions a user might ask about this dataset,
    specific to the columns available.
    Table: `{table_name}`
    Columns: {column_info}
    Past questions:
    {history}
    Return ONLY a JSON array of 4 strings, no extra text.
    """
    try:
        response = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": prompt}])
        raw = re.sub(r"```json|```", "", response["message"]["content"]).strip()
        suggestions = json.loads(raw)
        return suggestions if isinstance(suggestions, list) else []
    except Exception:
        return []
