import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

PALETTE = ["#E8A33D", "#1D9E75", "#7F77DD", "#BA7517", "#4FB7C7", "#D4537E"]


def _apply_style():
    plt.rcParams.update({
        "figure.facecolor": "#14181A",
        "axes.facecolor": "#14181A",
        "axes.edgecolor": "#2A3134",
        "axes.labelcolor": "#8B959A",
        "xtick.color": "#8B959A",
        "ytick.color": "#8B959A",
        "text.color": "#ECEEEE",
        "grid.color": "#2A3134",
        "grid.linestyle": "--",
    })


def plot_chart(df: pd.DataFrame) -> None:
    try:
        _apply_style()
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        text_cols = df.select_dtypes(exclude=["number"]).columns.tolist()

        if not text_cols and len(numeric_cols) >= 2:
            text_cols = [str(numeric_cols[0])]
            numeric_cols = numeric_cols[1:]

        if not numeric_cols:
            return

        if len(df) == 1 and len(df.columns) == 1:
            st.metric(label=numeric_cols[0], value=f"{df[numeric_cols[0]].iloc[0]:,.0f}")
            return

        date_col = None
        for col in text_cols:
            try:
                df[col] = pd.to_datetime(df[col])
                date_col = col
                break
            except (ValueError, TypeError):
                pass

        if date_col:
            y_col = numeric_cols[0]
            fig, ax = plt.subplots()
            ax.plot(df[date_col], df[y_col], marker="o", color=PALETTE[0])
            ax.set_xlabel(date_col)
            ax.set_ylabel(y_col)
            ax.set_title(f"{y_col} over time")
            plt.xticks(rotation=45)
            plt.tight_layout()
            st.pyplot(fig)
            return

        if text_cols and len(df) <= 6:
            x_col, y_col = text_cols[0], numeric_cols[0]
            fig, ax = plt.subplots()
            ax.pie(df[y_col], labels=df[x_col], autopct="%1.1f%%", colors=PALETTE)
            ax.set_title(f"{y_col} distribution")
            st.pyplot(fig)
            return

        if text_cols:
            x_col, y_col = text_cols[0], numeric_cols[0]
            fig, ax = plt.subplots()
            ax.bar(df[x_col].astype(str), df[y_col], color=PALETTE[0])
            ax.set_xlabel(x_col)
            ax.set_ylabel(y_col)
            ax.set_title(f"{y_col} by {x_col}")
            plt.xticks(rotation=45)
            plt.tight_layout()
            st.pyplot(fig)

    except Exception as e:
        st.write("Chart error:", e)
