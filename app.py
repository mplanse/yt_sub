import streamlit as st
import streamlit.components.v1 as components
import requests
import json
import os
import re
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi

# --- Configuración ---

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
CARPETA_ARTICULOS = "articulos"
MODELO_IA = "mistralai/mistral-nemo"

os.makedirs(CARPETA_ARTICULOS, exist_ok=True)


# --- Funciones auxiliares ---

def extraer_id_video(url):
    """Saca el ID de 11 caracteres de una URL de YouTube."""
    resultado = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
    if resultado:
        return resultado.group(1)
    return None


def obtener_subtitulos(video_id):
    """Descarga los subtítulos del video y los junta en un solo texto."""
    try:
        api = YouTubeTranscriptApi()
        transcripcion = api.fetch(video_id, languages=["es", "en"])
        texto = " ".join(trozo.text for trozo in transcripcion)
        return texto
    except Exception as e:
        st.error(f"No se pudieron obtener subtítulos: {e}")
        return None


def dividir_en_trozos(texto, palabras_por_trozo=1000):
    """Divide un texto largo en trozos de N palabras."""
    palabras = texto.split()
    trozos = []
    for i in range(0, len(palabras), palabras_por_trozo):
        trozo = " ".join(palabras[i:i + palabras_por_trozo])
        trozos.append(trozo)
    return trozos


def llamar_ia(texto, prompt_sistema):
    """Hace una llamada a OpenRouter con el texto y el prompt dado."""
    respuesta = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODELO_IA,
            "messages": [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": texto},
            ],
        },
    )

    datos = respuesta.json()

    if "choices" in datos and len(datos["choices"]) > 0:
        return datos["choices"][0]["message"]["content"]

    st.error(f"Error de la IA: {datos}")
    return None


def limpiar_con_ia(texto_crudo):
    """Divide el texto en trozos, limpia cada uno, y los junta."""

    prompt_primer_trozo = (
        "Eres un corrector de subtítulos automáticos. "
        "Te voy a pasar el texto de unos subtítulos de YouTube. "
        "Tu trabajo es SOLO corregir las palabras que estén claramente mal detectadas "
        "por el reconocimiento de voz. "
        "NO cambies la estructura del diálogo. "
        "NO reformules frases. "
        "NO añadas ni quites contenido. "
        "Mantén el texto exactamente como es, solo arregla los errores evidentes de transcripción. "
        "Devuelve el resultado en HTML simple: "
        "un título h1 basado en el tema del video, "
        "y separa en párrafos con etiquetas p donde haya pausas naturales. "
        "No uses markdown, solo HTML puro."
    )

    prompt_resto = (
        "Eres un corrector de subtítulos automáticos. "
        "Te voy a pasar una continuación del texto de unos subtítulos de YouTube. "
        "Tu trabajo es SOLO corregir las palabras que estén claramente mal detectadas "
        "por el reconocimiento de voz. "
        "NO cambies la estructura del diálogo. "
        "NO reformules frases. "
        "NO añadas ni quites contenido. "
        "Mantén el texto exactamente como es, solo arregla los errores evidentes de transcripción. "
        "Separa en párrafos con etiquetas p donde haya pausas naturales. "
        "No pongas título, solo párrafos. No uses markdown, solo HTML puro."
    )

    trozos = dividir_en_trozos(texto_crudo)
    partes_html = []

    for i, trozo in enumerate(trozos):
        if i == 0:
            resultado = llamar_ia(trozo, prompt_primer_trozo)
        else:
            resultado = llamar_ia(trozo, prompt_resto)

        if resultado is None:
            return None

        partes_html.append(resultado)

    return "\n".join(partes_html)


def guardar_articulo(video_id, html):
    """Guarda el HTML del artículo en la carpeta de artículos."""
    ruta = os.path.join(CARPETA_ARTICULOS, f"{video_id}.html")
    with open(ruta, "w", encoding="utf-8") as archivo:
        archivo.write(html)


def leer_articulo(video_id):
    """Lee el HTML guardado de un artículo."""
    ruta = os.path.join(CARPETA_ARTICULOS, f"{video_id}.html")
    with open(ruta, "r", encoding="utf-8") as archivo:
        return archivo.read()


def listar_articulos():
    """Devuelve la lista de video IDs que tienen artículo guardado."""
    archivos = os.listdir(CARPETA_ARTICULOS)
    ids = [nombre.replace(".html", "") for nombre in archivos if nombre.endswith(".html")]
    return ids


def articulo_existe(video_id):
    """Comprueba si ya existe un artículo para este video."""
    ruta = os.path.join(CARPETA_ARTICULOS, f"{video_id}.html")
    return os.path.exists(ruta)


# --- Interfaz ---

st.set_page_config(page_title="YT Subtítulos → Artículo", page_icon="📖", layout="centered")

# Inicializar el estado de la sesión
if "vista" not in st.session_state:
    st.session_state.vista = "inicio"
if "video_actual" not in st.session_state:
    st.session_state.video_actual = None


# ========== VISTA INICIO ==========
if st.session_state.vista == "inicio":

    st.title("📖 YouTube → Artículo")
    st.caption("Pega un link de YouTube, extrae los subtítulos y genera un artículo legible.")

    # --- Procesar nuevo video ---
    url = st.text_input("URL de YouTube", placeholder="https://www.youtube.com/watch?v=...")

    if st.button("Procesar", type="primary"):
        if not url:
            st.warning("Pega una URL primero.")
        else:
            video_id = extraer_id_video(url)

            if not video_id:
                st.error("No se pudo extraer el ID del video. Revisa la URL.")
            elif articulo_existe(video_id):
                st.info("Este video ya tiene artículo. Lo puedes leer abajo.")
            else:
                subtitulos = obtener_subtitulos(video_id)
                if subtitulos:
                    palabras_crudo = len(subtitulos.split())
                    st.info(f"Subtítulos extraídos: **{palabras_crudo} palabras**")

                    with st.expander("Ver subtítulos crudos"):
                        st.text(subtitulos[:2000] + ("..." if len(subtitulos) > 2000 else ""))

                    trozos = dividir_en_trozos(subtitulos)
                    total = len(trozos)
                    with st.spinner(f"Procesando con IA... {total} trozo(s) a procesar"):
                        html = limpiar_con_ia(subtitulos)
                    if html:
                        palabras_final = len(html.split())
                        st.info(f"Resultado: **{palabras_final} palabras** (de {palabras_crudo} originales)")
                        guardar_articulo(video_id, html)
                        st.success("¡Artículo generado y guardado!")

    # --- Lista de artículos guardados ---
    st.divider()
    st.subheader("Artículos guardados")

    articulos = listar_articulos()

    if not articulos:
        st.info("Aún no hay artículos. Procesa tu primer video arriba.")
    else:
        for vid in articulos:
            col1, col2 = st.columns([4, 1])
            with col1:
                if st.button(f"📄 {vid}", key=f"leer_{vid}"):
                    st.session_state.vista = "leer"
                    st.session_state.video_actual = vid
                    st.rerun()
            with col2:
                if st.button("🗑️", key=f"borrar_{vid}"):
                    os.remove(os.path.join(CARPETA_ARTICULOS, f"{vid}.html"))
                    st.rerun()


# ========== VISTA LECTURA ==========
elif st.session_state.vista == "leer":

    video_id = st.session_state.video_actual

    if st.button("← Volver"):
        st.session_state.vista = "inicio"
        st.session_state.video_actual = None
        st.rerun()

    st.caption(f"Video: {video_id}")

    html_articulo = leer_articulo(video_id)

    # Renderizar el artículo con JavaScript para guardar el progreso de lectura
    pagina_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{
            font-family: Georgia, serif;
            line-height: 1.8;
            padding: 20px 30px;
            max-width: 800px;
            margin: 0 auto;
            color: #e0e0e0;
            background-color: #0e1117;
        }}
        h1 {{
            color: #ffffff;
            font-size: 1.6em;
            margin-bottom: 0.8em;
            border-bottom: 1px solid #333;
            padding-bottom: 0.4em;
        }}
        h2, h3 {{
            color: #cccccc;
        }}
        p {{
            margin-bottom: 1em;
            text-align: justify;
        }}
    </style>
    </head>
    <body>
        {html_articulo}
        <div style="height: 40px;"></div>
        <script>
            const videoId = "{video_id}";
            const claveProgreso = "progreso_" + videoId;

            // Al cargar, restaurar posición guardada
            const guardado = localStorage.getItem(claveProgreso);
            if (guardado) {{
                setTimeout(function() {{
                    window.scrollTo(0, parseFloat(guardado));
                }}, 400);
            }}

            // Al hacer scroll, guardar posición
            window.addEventListener("scroll", function() {{
                localStorage.setItem(claveProgreso, window.scrollY);
            }});
        </script>
    </body>
    </html>
    """

    components.html(pagina_html, height=700, scrolling=True)
