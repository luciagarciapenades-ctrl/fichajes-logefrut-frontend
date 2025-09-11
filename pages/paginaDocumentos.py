# pages/paginaDocumentos.py
# pages/paginaDocumentos.py
import io, time, requests
from datetime import datetime
import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import fitz  # PyMuPDF

# App: login / menús (tu shim y helpers)
import supabase_login_shim as auth
import ui_pages as ui

st.set_page_config(page_title="Documentos", layout="wide")

# ---- Login y menú estándar de tu app ----
auth.generarLogin(__file__)  # ya corta si no hay sesión (según tu shim)
ui.generarMenuRoles(st.session_state.get("usuario", ""))  # o ui.generarMenu(...)

# ---- Supabase client (usa tus secrets) ----
from supabase import create_client

SUPABASE_URL = st.secrets["SUPABASE_URL"]
# Ojo: en tu proyecto la anon key está como VITE_SUPABASE_ANON_KEY
SUPABASE_ANON_KEY = st.secrets["VITE_SUPABASE_ANON_KEY"]

sb = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ---------- Identidad híbrida (Supabase Auth si existe; si no, login local CSV) ----------
def get_identity():
    # 1) Intentar sesión real de Supabase (si en algún momento haces sign_in desde Python)
    try:
        u = sb.auth.get_user()
        if u and u.user:
            email = (u.user.email or "").lower()
            return {
                "mode": "supabase",
                "user_id": u.user.id,              # uuid real
                "user_key": email,                 # texto (email)
                "user_name": email.split("@")[0],
                "slug": email.split("@")[0],       # por si lo usamos en Storage
            }
    except Exception:
        pass

    # 2) Fallback a tu login por CSV + cookie (st.session_state['usuario'])
    if "usuario" in st.session_state:
        key = str(st.session_state["usuario"]).strip().lower()
        return {
            "mode": "local",
            "user_id": None,
            "user_key": key,
            "user_name": key.split("@")[0],
            "slug": key.split("@")[0],
        }

    return None

ident = get_identity()
if not ident:
    st.warning("Acceso denegado. Inicia sesión.")
    st.stop()

user_id   = ident["user_id"]     # puede ser None si no hay Supabase Auth
user_key  = ident["user_key"]    # SIEMPRE disponible
user_name = ident["user_name"]
user_slug = ident["slug"]

# ---------- Catálogo de documentos (rutas públicas en bucket 'docs') ----------
DOCS = [
    {
        "id": "IT-01-02",
        "title": "IT 01/02 Buenas prácticas de higiene",
        "url": "https://qsxftklemuciiodwfeot.supabase.co/storage/v1/object/public/docs/IT%2001-02%20BUENAS%20PRACTICAS%20DE%20HIGIENE%20(1).pdf",
    },
    {
        "id": "IT-03-02",
        "title": "IT 03/02 BP uso EPI/utillaje (incluye lavado)",
        "url": "https://qsxftklemuciiodwfeot.supabase.co/storage/v1/object/public/docs/IT%2003-02%20BP%20uso%20rops%20protecciOn%20(incluye%20lavado).pdf",
    },
    {
        "id": "IT-03-02-C",
        "title": "IT 03/02 C Instrucción de carga y descarga",
        "url": "https://qsxftklemuciiodwfeot.supabase.co/storage/v1/object/public/docs/IT%2003-02%20C%20INSTRUCCION%20DE%20CARGA%20Y%20DESCARGA%20DE%20MERCANCIAS%20rev01.pdf",
    },
    {
        "id": "MED-OBL",
        "title": "Medidas de obligado cumplimiento",
        "url": "https://qsxftklemuciiodwfeot.supabase.co/storage/v1/object/public/docs/MEDIDA%20OBLIGATORIAS%20LOGEFRUT.pdf",
    },
]

st.subheader("Documentos")

# ---------- Traer firmas del usuario (por user_id si existe; si no, por user_key) ----------
q = sb.table("doc_signatures").select("*")
q = q.eq("user_id", user_id) if user_id else q.eq("user_key", user_key)
firmas = (q.execute().data) or []
firmas_by_id = {r["doc_id"]: r for r in firmas}

# ---------- Listado ----------
for doc in DOCS:
    st.divider()
    left, right = st.columns([2, 1], vertical_alignment="center")

    with left:
        st.subheader(doc["title"])
        st.link_button("🔍 Ver documento", doc["url"])

        if doc["id"] in firmas_by_id:
            f = firmas_by_id[doc["id"]]
            dt_iso = f.get("signed_at") or f.get("uploaded_at")
            if dt_iso:
                fecha_txt = dt_iso.split(".")[0].replace("T", " ")
                st.caption(f"✅ Firmado — {fecha_txt}")
            else:
                st.caption("✅ Firmado")
        else:
            st.caption("⏳ Pendiente")

    with right:
        if doc["id"] in firmas_by_id:
            st.success("Ya está firmado")
            continue

        with st.expander("✍️ Firmar este documento", expanded=False):
            st.write("Traza tu firma en el recuadro (puedes usar el dedo).")

            canvas_res = st_canvas(
                fill_color="rgba(0,0,0,0)",
                stroke_color="#000000",
                background_color="#FFFFFF",
                height=180,
                width=480,
                drawing_mode="freedraw",
                stroke_width=2,
                key=f"canvas_{doc['id']}",
            )

            firmar = st.button("Firmar y enviar", type="primary", key=f"btn_{doc['id']}")
            if firmar:
                # 1) Firma dibujada
                imgdata = getattr(canvas_res, "image_data", None)
                if imgdata is None or (hasattr(imgdata, "any") and not imgdata.any()):
                    st.warning("Dibuja tu firma antes de enviar.")
                    st.stop()

                # 2) Descarga PDF original
                try:
                    pdf_resp = requests.get(doc["url"], timeout=20)
                    pdf_resp.raise_for_status()
                    pdf_bytes = pdf_resp.content
                except Exception as e:
                    st.error(f"No se pudo descargar el PDF original: {e}")
                    st.stop()

                # 3) Convierte firma a PNG y recorta
                img = Image.fromarray(imgdata.astype("uint8")).convert("RGBA")
                bbox = img.getbbox()
                if bbox:
                    img = img.crop(bbox)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                sig_png = buf.getvalue()

                # 4) Estampa firma en la última página (abajo derecha)
                pdf_in = fitz.open(stream=pdf_bytes, filetype="pdf")
                page = pdf_in[-1]
                rect = page.rect

                pix = fitz.Pixmap(sig_png)
                target_w = 180
                scale = target_w / pix.width
                new_w = target_w
                new_h = int(pix.height * scale)

                x = rect.x1 - new_w - 36
                y = rect.y1 - new_h - 36
                page.insert_image(fitz.Rect(x, y, x + new_w, y + new_h), stream=sig_png)

                text = f"Firmado por {user_name} — {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                page.insert_text((36, rect.y1 - 36), text, fontsize=10, color=(0, 0, 0))

                out = io.BytesIO()
                pdf_in.save(out)
                pdf_in.close()
                signed_pdf = out.getvalue()

                # 5) Subir a Storage (bucket PRIVADO) guardando SOLO el PATH
                # Si hay uuid real, úsalo; si no, usa el slug textual (prefijo del usuario)
                path = f"signed/{(user_id or user_slug)}/{doc['id']}_{int(time.time())}.pdf"
                try:
                    sb.storage.from_("documentos_firmados").upload(
                        path, signed_pdf, {"content-type": "application/pdf"}
                    )
                except Exception as e:
                    st.error(f"No se pudo subir el documento firmado: {e}")
                    st.stop()

                # 6) Registrar en BD (siempre user_key; y user_id si existiera)
                payload = {
                    "doc_id": doc["id"],
                    "doc_title": doc["title"],
                    "signed_url": path,                           # PATH en el bucket privado
                    "signed_at": datetime.utcnow().isoformat(),   # para mostrar fecha
                    "user_key": user_key,
                }
                if user_id:
                    payload["user_id"] = user_id

                sb.table("doc_signatures").insert(payload).execute()

                st.success("Documento firmado y enviado correctamente.")
                st.toast("¡Firmado!")
                st.rerun()
