import os
import time
from google import genai
from google.genai import types

from dotenv import load_dotenv

load_dotenv()

def get_client():
    """Returns a configured Gemini client."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY no está configurada en .env")
    http_opts = types.HttpOptions(
        retry_options=types.HttpRetryOptions(attempts=1)
    )
    return genai.Client(api_key=api_key, http_options=http_opts)

AVAILABLE_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash",
    "gemini-3.7-flash"
]

def generate_with_fallback(client, contents):
    """
    Intenta generar contenido probando secuencialmente los modelos disponibles
    con failover inmediato (sin demoras por reintentos innecesarios en 503).
    """
    last_error = None
    for model_name in AVAILABLE_MODELS:
        try:
            print(f"[IA] Intentando con modelo: {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
            )
            print(f"[IA] Éxito con modelo: {model_name}")
            return response
        except Exception as e:
            err_str = str(e)
            print(f"[IA] Modelo {model_name} no disponible: {err_str[:120]}")
            last_error = e
            continue
    raise last_error


def download_youtube_video(url: str, output_path: str = "temp_video.mp4") -> str:
    """
    Descarga el video de YouTube en formato mp4.
    """
    import yt_dlp
    import uuid
    
    unique_id = str(uuid.uuid4())[:8]
    output_path = f"temp_inventario_{unique_id}.mp4"
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best',
        'outtmpl': output_path,
        'quiet': False,
        'no_warnings': True,
        'merge_output_format': 'mp4',
    }
    
    # Remove existing file if present
    if os.path.exists(output_path):
        os.remove(output_path)
        
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
        
    return output_path

def analyze_video_with_gemini(video_path: str) -> str:
    """
    Sube el video a Gemini y le pide que identifique los productos.
    Usa la nueva API google.genai (Client-based).
    """
    client = get_client()
    
    print("Subiendo {} a Gemini...".format(video_path).encode('ascii','ignore').decode())
    
    # Subir el archivo de video
    video_file = client.files.upload(file=video_path)
    
    print("Video subido como: {}. Esperando procesamiento...".format(video_file.name).encode('ascii','ignore').decode())
    
    # Esperar a que termine de procesar
    while video_file.state == "PROCESSING":
        print(".", end="", flush=True)
        time.sleep(3)
        video_file = client.files.get(name=video_file.name)
        
    if video_file.state == "FAILED":
        raise ValueError("El procesamiento del video en Gemini falló.")
        
    print("\nVideo listo. Analizando inventario...")
    
    prompt = """
Auditor de Inventarios por Visión (Retail)
ROL
Eres un auditor súper minucioso de inventarios en retail (supermercados, bodegas, abarrotes y ferreterías) con visión por computador. Tu prioridad es la EXHAUSTIVIDAD: debes mapear hasta el último rincón de los estantes y extraer la mayor cantidad posible de productos distintos. Un conteo incompleto es un error grave; un conteo con baja confianza pero completo es aceptable.

ENTRADA
Recibirás una imagen o un video de estanterías, góndolas o exhibidores.

Si es VIDEO: recorre los fotogramas en orden cronológico. Antes de listar un producto, verifica si ya lo registraste en un fotograma anterior comparando: (a) ubicación aproximada en el estante, (b) apariencia del empaque, y (c) el estante/zona al que pertenece. Si coincide, es el MISMO producto visto de nuevo — actualiza su registro (por ejemplo, si un ángulo nuevo revela mejor la marca) en vez de duplicarlo. Nunca sumes el mismo producto dos veces por verlo en distintos momentos.
Si es FOTO: analízala completa, incluyendo esquinas oscuras, bordes cortados, reflejos, estantes a ras de piso y los más altos.
PRINCIPIOS FUNDAMENTALES
No omitas nada. Si ves un producto borroso, lejano o parcialmente tapado, DEBES incluirlo en la lista. En esos casos, marca "marca": "No legible" y "confianza": "Baja", pero nunca lo dejes fuera del JSON.
No hay máximo de productos. Sigue buscando hasta agotar visualmente todo el anaquel. Una góndola típica suele tener más de 30 productos distintos; si tu lista tiene menos, vuelve a escanear antes de responder.
Diferencia estrictamente por variantes. Mismo tamaño pero distinto color, sabor o presentación → filas separadas (ej. "Snack bolsa roja", "Snack bolsa azul").
Nunca agrupes productos distintos en una sola línea. Papas, camotes y cebollas mezclados = TRES objetos JSON separados, nunca "Papas / Camotes / Cebollas". Prohibido usar "surtidos" o "varios" si puedes distinguir formas o colores.
Separa siempre lo CONTADO de lo ESTIMADO (ver campos cantidad_visible vs cantidad_estimada).
No inventes información. Nunca asumas una marca, precio o tamaño que no sea visible. Si no puedes leerlo, usa "No legible" o null. Está prohibido alucinar nombres de marca por familiaridad con el mercado.
PROCEDIMIENTO DE CONTEO
Zonificación: divide la imagen en una cuadrícula fina (filas de estante de arriba hacia abajo, columnas de izquierda a derecha) y escanea cada cuadrante con lupa mental. Usa esta cuadrícula para llenar el campo ubicacion de forma consistente (ej. "Estante 2 de 4, columna 3 de 5").
Conteo base: cuenta una por una las unidades frontales visibles. Ese número es cantidad_visible.
Profundidad: solo si hay evidencia visual (fondo del estante, cajas apiladas, espejo, ángulo lateral) estima cuántas unidades hay hacia el fondo → profundidad_estimada. Si no hay evidencia, profundidad_estimada = 1.
Fórmula: cantidad_estimada = round(cantidad_visible × profundidad_estimada).
rango_estimado = [floor(cantidad_estimada × 0.8), ceil(cantidad_estimada × 1.2)]. Si confianza = "Baja", amplía el rango a ±40% en vez de ±20%.
Productos a granel o densos (frutas, verduras, fideos apilados): cuenta una porción representativa y extrapola por el área visible; refleja la densidad real de la pila. Método: "muestreo_por_capas". En estos casos, usa unidad_medida acorde (kg, unidad, atado, etc.) en vez de asumir unidades sueltas.
Barrido final de rescate: vuelve a mirar la imagen/video completo buscando específicamente productos en sombras, al fondo del pasillo o en los extremos cortados. Agrégalos a la lista.
Autoverificación antes de responder: recuenta cuántos objetos JSON generaste vs. cuántas "manchas de producto" distintas recuerdas haber visto. Si hay discrepancia, vuelve a escanear en vez de responder de inmediato.
CATEGORÍAS PERMITIDAS
Abarrotes, Bebidas, Snacks y galletas, Lácteos y refrigerados, Limpieza, Cuidado personal, Frutas y verduras, Panadería, Congelados, Mascotas, Ferretería, Otros.

NIVELES DE CONFIANZA
Alta: producto y marca legibles, conteo directo sin obstrucciones.
Media: producto identificable pero marca/tamaño solo parcialmente visible.
Baja: identificación solo por forma/color, producto tapado o borroso (muy común, úsalo sin miedo — es preferible a omitir el producto).
ESQUEMA DE SALIDA (JSON)
Cada objeto de la lista debe seguir exactamente este esquema:

{
  "id": 1,
  "nombre_producto": "Producto + variedad/sabor + tamaño",
  "marca": "Marca o 'No legible'",
  "categoria": "Una de las categorías permitidas",
  "ubicacion": "Ej. 'Estante 2 de 4, columna 3 de 5, esquina derecha'",
  "unidad_medida": "unidad | kg | litro | paquete | docena | atado",
  "cantidad_visible": 0,
  "profundidad_estimada": 1,
  "cantidad_estimada": 0,
  "rango_estimado": [0, 0],
  "metodo_conteo": "conteo_directo | frentes_x_profundidad | muestreo_por_capas",
  "confianza": "Alta | Media | Baja",
  "precio_visible": "S/ 0.00 o null",
  "observaciones": "Ej. 'Parcialmente tapado por etiqueta'",
  "perecible": true,
  "fecha_caducidad": "DD/MM/YYYY o null"
}
RESTRICCIONES DE FORMATO (OBLIGATORIO)
Responde únicamente con el arreglo JSON válido. Nada de texto antes, después, ni bloques de markdown (```json).
No agregues explicaciones, resúmenes, ni comentarios fuera del JSON.
Usa comillas dobles, sin comas colgantes, sintaxis JSON estrictamente válida.
Si el estante está vacío o no se identifica ningún producto, responde [].
    """
    
    response = generate_with_fallback(
        client,
        contents=[
            types.Part.from_uri(
                file_uri=video_file.uri,
                mime_type=video_file.mime_type,
            ),
            prompt,
        ],
    )
    
    # Clean up the file from Google servers
    try:
        client.files.delete(name=video_file.name)
    except Exception:
        pass
    
    # Limpiar formato de respuesta (quitar ```json) si existe
    texto = response.text.strip()
    if texto.startswith("```json"):
        texto = texto.replace("```json", "", 1).strip()
    if texto.endswith("```"):
        texto = texto[:-3].strip()
        
    return texto

def analyze_website_with_gemini(url: str) -> str:
    """
    Descarga el HTML de la web, extrae el texto usando BeautifulSoup,
    y lo envía a Gemini para que extraiga los productos.
    """
    import requests
    from bs4 import BeautifulSoup
    
    client = get_client()
    print("[WEB] Descargando contenido de: {}".format(url).encode('ascii','ignore').decode())
    
    try:
        # Configurar headers para parecer un navegador normal y evitar bloqueos básicos
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        raise ValueError(f"Error al descargar la página web: {str(e)}")
        
    # Limpiar HTML y extraer texto junto con URLs de imágenes
    soup = BeautifulSoup(response.text, 'lxml')
    # Quitar scripts y estilos
    for script in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        script.extract()
        
    content_lines = []
    if soup.body:
        for element in soup.body.descendants:
            if element.name == 'img':
                src = element.get('src') or element.get('data-src') or element.get('data-original')
                if src and src.startswith('http'):
                    content_lines.append(f"[IMAGEN_URL: {src}]")
            elif isinstance(element, str):
                t = element.strip()
                if t:
                    content_lines.append(t)
    else:
        content_lines.append(soup.get_text(separator=' ', strip=True))
        
    text = " ".join(content_lines)
    
    # Limitar el tamaño del texto para no exceder los tokens de Gemini (ej. max 50000 caracteres)
    text = text[:50000]
    
    print("[IA] Pagina procesada. Analizando catalogo con Gemini...")
    
    prompt = f"""
    Eres un auditor experto de inventarios retail, supermercados y ferreterías.
    A continuación, te presento el texto extraído de la página web de un catálogo o tienda virtual.
    Tu tarea es analizar cuidadosamente este texto e identificar todos los productos individuales que se están vendiendo 
    (marcas, herramientas, materiales, abarrotes, tipos de producto, precios, etc.).
    
    TEXTO DE LA PÁGINA WEB:
    \"\"\"
    {text}
    \"\"\"
    
    Devuelve la información estrictamente en formato JSON, siendo una lista de objetos.
    Cada objeto debe tener esta estructura:
    {{
      "nombre_producto": "Ej. Taladro Inalámbrico Bosch 18V",
      "marca": "Ej. Bosch",
      "categoria": "Ej. Herramientas",
      "cantidad_estimada": "Ej. 1",
      "confianza": "Alta/Media/Baja",
      "image_url": "Coloca aquí la [IMAGEN_URL: ...] que le corresponde al producto, si la encontraste cerca del texto.",
      "perecible": true,
      "fecha_caducidad": "DD/MM/YYYY o null"
    }}
    No agregues ningún texto fuera del JSON (ni formato markdown).
    """
    
    resp = generate_with_fallback(
        client,
        contents=[prompt],
    )
    
    # Limpiar formato de respuesta
    texto = resp.text.strip()
    if texto.startswith("```json"):
        texto = texto.replace("```json", "", 1).strip()
    if texto.endswith("```"):
        texto = texto[:-3].strip()
        
    return texto


def analyze_zoned_image_with_gemini(image_path: str, zones: list) -> str:
    """
    Analiza una imagen con zonas definidas usando Gemini Vision.
    Recibe la ruta de la imagen y una lista de zonas (cada zona con nombre y coordenadas),
    y devuelve un JSON con los productos detectados en cada zona.
    """
    import PIL.Image
    import base64

    client = get_client()

    # Leer imagen en base64
    with open(image_path, "rb") as f:
        image_data = f.read()

    # Construir descripción de zonas para el prompt
    zones_description = ""
    for i, zone in enumerate(zones):
        name = zone.get("name", f"Zona {i+1}")
        zones_description += f"- {name}\n"

    prompt = f"""Eres un auditor experto de inventarios retail. Te presento una imagen de una tienda o almacén.
La imagen ha sido dividida en las siguientes zonas por el usuario:
{zones_description}

Tu tarea:
1. Analiza TODA la imagen e identifica todos los productos visibles.
2. Para cada producto, indica en qué zona se encuentra según las zonas definidas.
3. Devuelve la información estrictamente en formato JSON: una lista de objetos.

Cada objeto debe tener esta estructura:
{{
  "nombre_producto": "Nombre descriptivo del producto",
  "marca": "Marca si es visible, si no 'Sin marca'",
  "categoria": "Categoría del producto",
  "cantidad_estimada": "Número estimado de unidades visibles",
  "zona": "Nombre de la zona donde está el producto",
  "confianza": "Alta/Media/Baja",
  "perecible": true,
  "fecha_caducidad": "DD/MM/YYYY o null"
}}

No agregues ningún texto fuera del JSON (ni formato markdown ni explicaciones).
"""

    # Enviar imagen como bytes inline
    image_part = types.Part.from_bytes(data=image_data, mime_type="image/jpeg")

    resp = generate_with_fallback(
        client,
        contents=[image_part, prompt],
    )

    texto = resp.text.strip()
    if texto.startswith("```json"):
        texto = texto.replace("```json", "", 1).strip()
    if texto.endswith("```"):
        texto = texto[:-3].strip()

    return texto
