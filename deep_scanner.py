import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import json
import traceback

# Dictionary to hold job status in memory
# Key: job_id, Value: {"status": "running|completed|error", "progress": str, "data": list, "error": str}
SCAN_JOBS = {}

async def _deep_scan_worker(job_id: str, url: str, max_pages: int = 5):
    from video_processor import analyze_website_with_gemini
    from db import match_products_with_db
    
    SCAN_JOBS[job_id] = {
        "status": "running",
        "progress": "Iniciando navegador fantasma...",
        "data": [],
        "error": None
    }
    
    all_products = []
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            SCAN_JOBS[job_id]["progress"] = f"Cargando pagina inicial: {url[:30]}..."
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            for current_page in range(1, max_pages + 1):
                SCAN_JOBS[job_id]["progress"] = f"Escaneando pagina {current_page} (extrayendo DOM)..."
                
                # Esperar a que el JS renderice productos y se acomode el layout
                await page.wait_for_timeout(5000)
                
                # Desplazarse hacia abajo para activar Lazy Loading
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)
                await page.evaluate("window.scrollTo(0, 0)")
                
                html = await page.content()
                soup = BeautifulSoup(html, 'lxml')
                for script in soup(['script', 'style', 'noscript', 'header', 'footer']):
                    script.extract()
                    
                text_content = soup.get_text(separator=' ', strip=True)[:50000]
                
                SCAN_JOBS[job_id]["progress"] = f"Analizando pagina {current_page} con IA..."
                json_str = analyze_website_with_gemini(text_content) # Reusamos la funcion adaptada de video_processor
                
                try:
                    page_products = json.loads(json_str)
                    if isinstance(page_products, list):
                        all_products.extend(page_products)
                except json.JSONDecodeError:
                    print(f"[DEEP-SCAN] Fallo parseo JSON en pag {current_page}")
                
                # Update progress
                SCAN_JOBS[job_id]["progress"] = f"Pagina {current_page} completada. {len(all_products)} items encontrados en total. Buscando Siguiente pagina..."
                
                if current_page == max_pages:
                    break
                    
                # Intentar buscar boton "Siguiente" o "Next" o ">"
                next_selectors = [
                    "button[id='testId-pagination-bottom-arrow-right']", # Sodimac exact selector
                    "button:has-text('Siguiente')",
                    "a:has-text('Siguiente')",
                    "a:has-text('Next')",
                    "button:has-text('Next')",
                    "[aria-label='Siguiente']",
                    "[aria-label='Next']",
                    "a:has-text('>')",
                    ".next",
                    ".pagination-next"
                ]
                
                clicked = False
                for selector in next_selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element and await element.is_visible():
                            await element.click()
                            SCAN_JOBS[job_id]["progress"] = f"Navegando a pagina {current_page + 1}..."
                            await page.wait_for_load_state("domcontentloaded", timeout=30000)
                            clicked = True
                            break
                    except Exception:
                        pass
                        
                if not clicked:
                    print("[DEEP-SCAN] No se encontro boton de Siguiente. Terminando.")
                    break
                    
            await browser.close()
            
        # Match con Caserita
        SCAN_JOBS[job_id]["progress"] = "Cruzando datos con el Inventario Maestro (Caserita)..."
        final_products = match_products_with_db(all_products)
        
        SCAN_JOBS[job_id]["status"] = "completed"
        SCAN_JOBS[job_id]["progress"] = f"Escaneo Profundo finalizado con exito. {len(final_products)} productos procesados."
        SCAN_JOBS[job_id]["data"] = final_products

    except Exception as e:
        print(f"[DEEP-SCAN] Error: {traceback.format_exc()}")
        SCAN_JOBS[job_id]["status"] = "error"
        SCAN_JOBS[job_id]["error"] = str(e)
        SCAN_JOBS[job_id]["progress"] = f"Error: {str(e)}"

def run_deep_scan(job_id: str, url: str, max_pages: int = 5):
    """
    Wrapper sincrono para lanzar el escaneo asincrono en un nuevo event loop.
    Necesario para BackgroundTasks de FastAPI.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_deep_scan_worker(job_id, url, max_pages))
    loop.close()
