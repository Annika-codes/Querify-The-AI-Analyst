import streamlit as st

QUERIFY_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }

:root {
    --qz-border: #2A3134;
    --qz-muted: #8B959A;
    --qz-accent: #E8A33D;
}

.stApp { background-color: #14181A !important; }

[data-testid="stSidebar"] {
    background-color: #1B2023;
    border-right: 1px solid var(--qz-border);
}

[data-testid="stMetric"] {
    background-color: #14181A;
    border: 1px solid var(--qz-border);
    border-radius: 10px;
    padding: 10px 14px;
}
[data-testid="stMetricValue"] { font-family: 'IBM Plex Mono', monospace; font-weight: 500; }

[data-testid="stChatMessage"] {
    border: 1px solid var(--qz-border);
    border-radius: 12px;
    background-color: #1B2023;
}

.stButton > button {
    border: 1px solid var(--qz-border);
    border-radius: 8px;
    background-color: transparent;
}
.stButton > button:hover { border-color: var(--qz-accent); color: var(--qz-accent); }
.stButton > button[kind="primary"] {
    background-color: var(--qz-accent);
    color: #14181A;
    border: none;
    font-weight: 500;
}

code, pre, [data-testid="stCodeBlock"] {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 12px !important;
}

[data-testid="stDataFrame"] { border: 1px solid var(--qz-border); border-radius: 8px; }
[data-testid="stDataFrame"] * { font-family: 'IBM Plex Mono', monospace !important; font-size: 12.5px !important; }

[data-testid="stFileUploaderDropzone"] {
    border: 1px dashed var(--qz-border);
    border-radius: 12px;
    background-color: transparent;
}
</style>
"""


def apply_theme() -> None:
    st.markdown(QUERIFY_CSS, unsafe_allow_html=True)


TYPE_DOT_COLORS = {"numeric": "#1D9E75", "categorical": "#BA7517", "date": "#7F77DD"}


def column_type_dot(kind: str) -> str:
    color = TYPE_DOT_COLORS.get(kind, "#8B959A")
    return (
        f'<span style="display:inline-block;width:7px;height:7px;'
        f'border-radius:50%;background:{color};margin-right:6px;"></span>'
    )
