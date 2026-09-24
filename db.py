import os
from supabase import create_client, Client

def get_supabase() -> Client:
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("[SUPABASE] Advertencia: SUPABASE_URL o SUPABASE_KEY no definidos.")
        return None
    return create_client(url, key)

def match_products_with_db(products: list) -> list:
    """
    Toma la lista de productos detectados por la IA e intenta encontrar
    una coincidencia en la base de datos de Caserita (tabla `inventario`).
    Si la encuentra, adjunta la `image_url` y otros datos relevantes.
    """
    supabase = get_supabase()
    if not supabase:
        return products
        
    for product in products:
        try:
            nombre = product.get("nombre_producto", "")
            if not nombre:
                continue
                
            # Buscar en la tabla inventario usando busqueda de texto o ILIKE
            search_term = f"%{nombre.split()[0]}%" if len(nombre.split()) > 0 else f"%{nombre}%"
            
            response = supabase.table("inventario").select("*").ilike("nombre_producto", search_term).limit(1).execute()
            
            if response.data and len(response.data) > 0:
                match = response.data[0]
                # Inyectar datos de Caserita si hay imagen, de lo contrario conservar la extraída (ej. web)
                db_image = match.get("image_url")
                if db_image:
                    product["image_url"] = db_image
                product["caserita_match"] = True
                
                safe_nombre_supa = nombre.encode('ascii', 'ignore').decode('ascii')
                safe_match_supa = match.get('nombre_producto', '').encode('ascii', 'ignore').decode('ascii')
                print(f"[SUPABASE] Match encontrado para: {safe_nombre_supa} -> {safe_match_supa}")
            else:
                product["caserita_match"] = False
            
            # FALLBACK WEB: Si no se encontró en Caserita y no hay foto, buscamos en internet
            if not product.get("image_url"):
                import time
                from duckduckgo_search import DDGS
                
                safe_nombre = nombre.encode('ascii', 'ignore').decode('ascii')
                print(f"[WEB-SEARCH] Buscando imagen referencial para: {safe_nombre}")
                try:
                    time.sleep(1) # Pausa de 1 seg para evitar el error 403 Rate Limit de DuckDuckGo
                    with DDGS() as ddgs:
                        # Buscamos la primera imagen (limit=1)
                        results = list(ddgs.images(f"{nombre} producto", max_results=1))
                        if results:
                            product["image_url"] = results[0]["image"]
                            print(f"[WEB-SEARCH] Imagen encontrada: {results[0]['image'][:50]}...")
                except Exception as e:
                    print(f"[WEB-SEARCH] Error buscando imagen: {str(e)[:50]}")
                    
        except Exception as e:
            print(f"[SUPABASE] Error buscando producto '{nombre}': {e}")
            
            
    return products

def save_draft_inventory(user_id: str, products: list) -> bool:
    """Guarda o actualiza productos en el inventario borrador del usuario."""
    supabase = get_supabase()
    if not supabase: return False
    
    # Simple strategy: insert all. In a real app, we might upsert based on nombre_producto + user_id.
    # For now, we will just insert them. The frontend handles merging locally before sending, 
    # but to be robust, we can clear the draft and re-insert, OR upsert.
    # We will do a full replace for simplicity of the draft sync:
    try:
        supabase.table("inventario_borrador").delete().eq("user_id", user_id).execute()
        
        if not products:
            return True
            
        rows = []
        for p in products:
            rows.append({
                "user_id": user_id,
                "nombre_producto": p.get("nombre_producto", "Sin nombre"),
                "marca": p.get("marca"),
                "categoria": p.get("categoria"),
                "cantidad_estimada": int(p.get("cantidad_estimada", 0)),
                "unidad_medida": p.get("unidad_medida"),
                "precio_visible": p.get("precio_visible"),
                "costo_unitario": p.get("costo_unitario"),
                "ubicacion": p.get("ubicacion"),
                "confianza": p.get("confianza"),
                "image_url": p.get("image_url"),
                "perecible": bool(p.get("perecible", False)),
                "fecha_caducidad": p.get("fecha_caducidad") if p.get("fecha_caducidad") != "null" else None
            })
        supabase.table("inventario_borrador").insert(rows).execute()
        return True
    except Exception as e:
        print(f"[SUPABASE] Error guardando borrador: {e}")
        return False

def get_draft_inventory(user_id: str) -> list:
    """Obtiene el inventario borrador del usuario."""
    supabase = get_supabase()
    if not supabase: return []
    try:
        # Sort by updated time to show latest
        response = supabase.table("inventario_borrador").select("*").eq("user_id", user_id).order("fecha_actualizacion", desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"[SUPABASE] Error obteniendo borrador: {e}")
        return []
