import os, streamlit as st
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_ANON_KEY")
_client = None
def _get_client():
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            raise RuntimeError("Falta SUPABASE_URL / SUPABASE_ANON_KEY (env o st.secrets)")
        _client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return _client

def generarLogin(_archivo:str=""):
    """Imita tu login original: establece st.session_state['usuario'] y ['user_id']."""
    if st.session_state.get("user_id"):
        return
    st.subheader("Iniciar sesión")
    email = st.text_input("Email")
    pwd   = st.text_input("Contraseña", type="password")
    col1, col2 = st.columns(2)
    if col1.button("Entrar") and email and pwd:
        try:
            res = _get_client().auth.sign_in_with_password({"email": email, "password": pwd})
            st.session_state["user_id"] = res.user.id
            # Para tu app usamos el email como 'usuario' (lo que esperaban tus pantallas)
            st.session_state["usuario"] = res.user.email
            st.success("Sesión iniciada")
            st.rerun()
        except Exception as e:
            st.error(f"Error al iniciar sesión: {e}")
            st.stop()
    if col2.button("Crear cuenta") and email and pwd:
        try:
            _get_client().auth.sign_up({"email": email, "password": pwd})
            st.info("Revisa tu email para confirmar la cuenta y vuelve a iniciar sesión.")
        except Exception as e:
            st.error(f"Error al crear cuenta: {e}")
    if not st.session_state.get("user_id"):
        st.stop()
