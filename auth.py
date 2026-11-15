import bcrypt
import streamlit as st

from config import APP_USERNAME, APP_PASSWORD_HASH


def require_login() -> None:
    """Blocks the rest of the app until the user signs in successfully."""
    if st.session_state.get("authenticated"):
        return

    st.markdown("### Sign in to Querify")

    if not APP_PASSWORD_HASH:
        st.error(
            "No password is configured yet. Set QUERIFY_APP_PASSWORD_HASH "
            "in your environment (see .env.example for how to generate one)."
        )
        st.stop()

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Sign in", type="primary"):
        valid_user = username == APP_USERNAME
        valid_pass = valid_user and bcrypt.checkpw(
            password.encode(), APP_PASSWORD_HASH.encode()
        )
        if valid_user and valid_pass:
            st.session_state["authenticated"] = True
            st.session_state["current_user"] = username
            st.rerun()
        else:
            st.error("Incorrect username or password.")

    st.stop()
