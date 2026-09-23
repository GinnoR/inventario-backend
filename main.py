import os
from fastapi import FastAPI, HTTPException, File, UploadFile, BackgroundTasks, Depends, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import json
import traceback
from typing import List, Optional, Any

# Nuevas importaciones para SaaS
from sqlalchemy.orm import Session
from database import engine, get_db
import models
import auth

load_dotenv()

# Crear tablas de la base de datos
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Caserita Smart - AI Backend SaaS")

app.include_router(auth.router)

# Habilitar CORS para que el frontend pueda comunicarse
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://10.26.1.167:3000",
        "http://192.168.56.1:3000",
        "https://frontend-three-kappa-24.vercel.app",       # Vercel alias
        "https://frontend-1zybkqbu7-ginno-riveras-projects.vercel.app",  # Vercel deploy
        "https://*.vercel.app",                              # Cualquier deploy de Vercel
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.get("/")
def read_root():
    return {"message": "Motor de Inteligencia Artificial (Inventario Por Imagenes) Activo"}

# --- VIDEO AND WEB PROCESSING ---
from video_processor import download_youtube_video, analyze_video_with_gemini, analyze_website_with_gemini, analyze_zoned_image_with_gemini

class VideoRequest(BaseModel):
    youtube_url: str

@app.post("/api/inventory/process-video")
def process_video_endpoint(req: VideoRequest, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """
    Endpoint que recibe un link de YT o una URL de tienda web, 
    y lo pasa a Gemini para extraer el inventario.
    """
    if current_user.credits <= 0:
        raise HTTPException(status_code=402, detail="No tienes créditos suficientes. Por favor, recarga tu cuenta.")
        
    try:
        url = req.youtube_url.strip()
        is_youtube = "youtube.com" in url or "youtu.be" in url
        
        if is_youtube:
            # 1. Descargar video
            print(f"[DESCARGA] Descargando video: {url}")
            video_path = download_youtube_video(url)
            
            # 2. Analizar con Gemini
            print("[IA] Enviando a Gemini para analisis...")
            json_result_str = analyze_video_with_gemini(video_path)
            
            # 3. Limpiar archivo temporal
            if os.path.exists(video_path):
                os.remove(video_path)
                print("[LIMPIEZA] Video temporal eliminado")
        else:
            # Flujo web
            print(f"[WEB] Iniciando analisis de pagina web: {url}")
            json_result_str = analyze_website_with_gemini(url)
        
        # 4. Parsear a diccionario
        try:
            productos = json.loads(json_result_str)
        except json.JSONDecodeError:
            return {
                "status": "partial_success", 
                "raw_text": json_result_str,
                "error": "Gemini no devolvió un JSON válido"
            }
            
        # 5. Cruzar con base de datos de Caserita
        from db import match_products_with_db
        if isinstance(productos, list):
            productos = match_products_with_db(productos)
            
        # Deducir 1 credito
        current_user.credits -= 1
        db.commit()
        
        # Guardar Job en DB
        new_job = models.InventoryJob(
            user_id=current_user.id,
            video_url=url,
            status="completed",
            result_json=json.dumps(productos)
        )
        db.add(new_job)
        db.commit()
            
        return {
            "status": "success", 
            "detected_items": len(productos) if isinstance(productos, list) else 1, 
            "data": productos,
            "credits_remaining": current_user.credits
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] {error_msg}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/api/inventory/process-zoned-image")
async def process_zoned_image_endpoint(
    file: UploadFile = File(...), 
    zones: str = Form(...),
    current_user: models.User = Depends(auth.get_current_user), 
    db: Session = Depends(get_db)
):
    import shutil
    import uuid
    from db import match_products_with_db
    
    try:
        zones_data = json.loads(zones)
        temp_filename = f"temp_upload_{uuid.uuid4().hex[:8]}_{file.filename}"
        print(f"[UPLOAD] Recibiendo imagen zonificada: {file.filename}")
        
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        print("[IA] Enviando imagen zonificada a Gemini para analisis...")
        json_result_str = analyze_zoned_image_with_gemini(temp_filename, zones_data)
        
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
            
        try:
            productos = json.loads(json_result_str)
        except json.JSONDecodeError:
            return {
                "status": "partial_success", 
                "raw_text": json_result_str,
                "error": "Gemini no devolvió un JSON válido"
            }
            
        if isinstance(productos, list):
            productos = match_products_with_db(productos)
            
        new_job = models.InventoryJob(
            user_id=current_user.id,
            video_url="zoned_image",
            status="completed",
            result_json=json.dumps(productos)
        )
        db.add(new_job)
        db.commit()
            
        return {
            "status": "success", 
            "detected_items": len(productos) if isinstance(productos, list) else 1, 
            "data": productos,
            "credits_remaining": current_user.credits
        }
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] {error_msg}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/api/inventory/upload-video")
async def upload_video_endpoint(file: UploadFile = File(...), current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """
    Endpoint que recibe un archivo de video local y lo pasa a Gemini.
    """
    import shutil
    import uuid
    from db import match_products_with_db
    import traceback
    
    if False:
        raise HTTPException(status_code=402, detail="No tienes créditos suficientes. Por favor, recarga tu cuenta.")
        
    try:
        # Generar nombre único
        temp_filename = f"temp_upload_{uuid.uuid4().hex[:8]}_{file.filename}"
        
        print(f"[UPLOAD] Recibiendo archivo local: {file.filename}")
        
        # Guardar archivo localmente
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Analizar con Gemini
        print("[IA] Enviando video local a Gemini para analisis...")
        json_result_str = analyze_video_with_gemini(temp_filename)
        
        # Limpiar
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
            print("[LIMPIEZA] Video local temporal eliminado")
            
        # Parsear a diccionario
        try:
            productos = json.loads(json_result_str)
        except json.JSONDecodeError:
            return {
                "status": "partial_success", 
                "raw_text": json_result_str,
                "error": "Gemini no devolvió un JSON válido"
            }
            
        if isinstance(productos, list):
            productos = match_products_with_db(productos)
            
        current_user.credits -= 1
        db.commit()
        
        new_job = models.InventoryJob(
            user_id=current_user.id,
            video_url="local_upload",
            status="completed",
            result_json=json.dumps(productos)
        )
        db.add(new_job)
        db.commit()
            
        return {
            "status": "success",
            "source": "local_video",
            "detected_items": len(productos) if isinstance(productos, list) else 1,
            "data": productos,
            "credits_remaining": current_user.credits
        }
        
    except Exception as e:
        print(f"[ERROR] {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

# --- DEEP SCAN ENDPOINTS ---
from deep_scanner import run_deep_scan, SCAN_JOBS
import uuid

class DeepScanRequest(BaseModel):
    url: str
    max_pages: int = 5

@app.post("/api/inventory/deep-scan")
def deep_scan_endpoint(req: DeepScanRequest, background_tasks: BackgroundTasks):
    job_id = uuid.uuid4().hex
    # Enviar a background task
    background_tasks.add_task(run_deep_scan, job_id, req.url, req.max_pages)
    return {"job_id": job_id, "status": "started"}

@app.get("/api/inventory/job-status/{job_id}")
def job_status_endpoint(job_id: str):
    if job_id not in SCAN_JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    return SCAN_JOBS[job_id]

# --- EXCEL EXPORT ---
from excel_exporter import generate_inventory_excel

class ProductItem(BaseModel):
    model_config = {"extra": "ignore"}
    nombre_producto: str = ""
    marca: str = ""
    categoria: str = ""
    cantidad_estimada: Any = "0"
    confianza: str = "Baja"
    image_url: Optional[str] = None
    ubicacion: Optional[str] = None
    cantidad_visible: Any = None
    profundidad_estimada: Any = None
    rango_estimado: Any = None
    metodo_conteo: Optional[str] = None
    observaciones: Optional[str] = None


class ExportRequest(BaseModel):
    products: List[ProductItem]

@app.post("/api/inventory/export-xlsx")
def export_xlsx_endpoint(req: ExportRequest):
    """
    Recibe la lista de productos detectados y devuelve un archivo .xlsx
    con imágenes incrustadas, alturas de fila apropiadas y formato profesional.
    """
    try:
        products_dicts = [p.model_dump() for p in req.products]
        print(f"[EXCEL] Generando Excel con {len(products_dicts)} productos...")
        
        buffer = generate_inventory_excel(products_dicts)
        
        print("[EXCEL] Archivo generado exitosamente")
        
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=inventario_detectado.xlsx"
            }
        )
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR EXCEL] {error_msg}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=error_msg)

from html_exporter import generate_inventory_html

@app.post("/api/inventory/export-html")
def export_html_endpoint(req: ExportRequest):
    """
    Recibe la lista de productos detectados y devuelve un archivo .html
    con imágenes incrustadas en base64 y formato profesional.
    """
    try:
        products_dicts = [p.model_dump() for p in req.products]
        print(f"[HTML] Generando HTML con {len(products_dicts)} productos...")
        
        html_str = generate_inventory_html(products_dicts)
        
        from fastapi.responses import HTMLResponse
        print("[HTML] Archivo generado exitosamente")
        
        return HTMLResponse(
            content=html_str,
            headers={
                "Content-Disposition": "attachment; filename=inventario_detectado.html"
            }
        )
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR HTML] {error_msg}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=error_msg)

# --- BILLING & CREDITS ---
class RechargeRequest(BaseModel):
    amount: int

@app.post("/api/billing/recharge")
def recharge_credits_endpoint(req: RechargeRequest, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """
    Endpoint simulado para recargar créditos. En producción, esto sería un webhook de Stripe/MercadoPago.
    """
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
        
    current_user.credits += req.amount
    db.commit()
    
    return {"status": "success", "message": f"{req.amount} créditos agregados.", "new_balance": current_user.credits}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

