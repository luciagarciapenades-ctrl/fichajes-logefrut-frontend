import os, requests, datetime as dt

BASE = (os.getenv("BACKEND_BASE_URL") or "http://localhost:8000").rstrip("/")

def _r(method, path, **kw):
    resp = requests.request(method, f"{BASE}{path}", timeout=30, **kw)
    resp.raise_for_status()
    return resp.json() if resp.content else None

# ---- Fichajes ----
def post_fichaje(user_id: str, empleado: str, tipo: str, observ: str="", fuente="movil"):
    data = {"user_id": user_id, "empleado": empleado or "", "tipo": tipo,
            "observaciones": observ or "", "fuente": fuente}
    return _r("POST", "/fichajes", data=data)

def get_fichajes(user_id: str, limit: int = 200):
    return _r("GET", "/fichajes", params={"user_id": user_id, "limit": limit})

# ---- Vacaciones ----
def post_vacaciones(user_id: str, usuario: str, fi, ff, dias: int, comentario=""):
    data = {"user_id": user_id, "usuario": usuario, "fecha_inicio": str(fi),
            "fecha_fin": str(ff), "dias": int(dias), "comentario": comentario or ""}
    return _r("POST", "/vacaciones", data=data)

def get_vacaciones(user_id: str):
    return _r("GET", "/vacaciones", params={"user_id": user_id})

def cancel_vacacion(user_id: str, vac_id: int):
    return _r("POST", "/vacaciones/cancel", data={"user_id": user_id, "id": int(vac_id)})

# ---- Bajas / permisos ----
def post_baja(user_id: str, usuario: str, tipo: str, fi, ff, descripcion: str, files):
    data = {"user_id": user_id, "usuario": usuario, "tipo": tipo,
            "fecha_inicio": str(fi), "fecha_fin": (str(ff) if ff else ""),
            "descripcion": descripcion or ""}
    # files = lista de UploadedFile de Streamlit → multipart:
    fls = [("files", (f.name, f.getbuffer())) for f in (files or [])]
    return _r("POST", "/bajas", data=data, files=fls)

def get_bajas(user_id: str):
    return _r("GET", "/bajas", params={"user_id": user_id})



