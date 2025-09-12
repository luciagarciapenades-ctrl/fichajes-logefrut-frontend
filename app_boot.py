import streamlit as st

def boot():
    st.set_page_config(
        layout="wide",
        initial_sidebar_state="collapsed",
        menu_items={"Get help": None, "Report a bug": None, "About": None}
    )
    st.markdown("""
    <style>
      /* Ocultar menú 3 puntos y footer */
      div[data-testid="stMainMenu"] { visibility: hidden; }
      #MainMenu { visibility: hidden; } /* compat */
      footer { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)
