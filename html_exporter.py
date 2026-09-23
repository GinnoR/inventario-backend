import base64
import os
from typing import List, Dict, Any

CATEGORY_CONFIG = {
    'abarrotes':        {'emoji': '🛒', 'color': '#F59E0B', 'bg': '#FEF3C7'},
    'bebidas':          {'emoji': '🥤', 'color': '#06B6D4', 'bg': '#CFFAFE'},
    'lácteos':          {'emoji': '🥛', 'color': '#3B82F6', 'bg': '#DBEAFE'},
    'lacteos':          {'emoji': '🥛', 'color': '#3B82F6', 'bg': '#DBEAFE'},
    'limpieza':         {'emoji': '🧹', 'color': '#14B8A6', 'bg': '#CCFBF1'},
    'snacks':           {'emoji': '🍿', 'color': '#F97316', 'bg': '#FED7AA'},
    'galletas':         {'emoji': '🍪', 'color': '#CA8A04', 'bg': '#FEF9C3'},
    'enlatados':        {'emoji': '🥫', 'color': '#EF4444', 'bg': '#FEE2E2'},
    'conservas':        {'emoji': '🥫', 'color': '#EF4444', 'bg': '#FEE2E2'},
    'condimentos':      {'emoji': '🧂', 'color': '#EAB308', 'bg': '#FEF9C3'},
    'salsas':           {'emoji': '🫙', 'color': '#F43F5E', 'bg': '#FFE4E6'},
    'cuidado personal': {'emoji': '🧴', 'color': '#EC4899', 'bg': '#FCE7F3'},
    'higiene':          {'emoji': '🧼', 'color': '#8B5CF6', 'bg': '#EDE9FE'},
    'frutas':           {'emoji': '🍎', 'color': '#22C55E', 'bg': '#DCFCE7'},
    'verduras':         {'emoji': '🥬', 'color': '#10B981', 'bg': '#D1FAE5'},
    'carnes':           {'emoji': '🥩', 'color': '#DC2626', 'bg': '#FEE2E2'},
    'panadería':        {'emoji': '🍞', 'color': '#D97706', 'bg': '#FDE68A'},
    'cereales':         {'emoji': '🥣', 'color': '#FBBF24', 'bg': '#FEF3C7'},
    'aceites':          {'emoji': '🫒', 'color': '#84CC16', 'bg': '#ECFCCB'},
    'pastas':           {'emoji': '🍝', 'color': '#EAB308', 'bg': '#FEF9C3'},
    'mascotas':         {'emoji': '🐕', 'color': '#8B5CF6', 'bg': '#EDE9FE'},
    'embutidos':        {'emoji': '🌭', 'color': '#F97316', 'bg': '#FFEDD5'},
    'herramientas':     {'emoji': '🔨', 'color': '#64748B', 'bg': '#F1F5F9'},
    'ferretería':       {'emoji': '🔩', 'color': '#475569', 'bg': '#E2E8F0'},
    'ferreteria':       {'emoji': '🔩', 'color': '#475569', 'bg': '#E2E8F0'},
    'electricidad':     {'emoji': '🔌', 'color': '#EAB308', 'bg': '#FEF9C3'},
    'línea sanitaria':  {'emoji': '🚰', 'color': '#3B82F6', 'bg': '#DBEAFE'},
    'linea sanitaria':  {'emoji': '🚰', 'color': '#3B82F6', 'bg': '#DBEAFE'},
    'fontanería':       {'emoji': '🚰', 'color': '#3B82F6', 'bg': '#DBEAFE'},
    'fontaneria':       {'emoji': '🚰', 'color': '#3B82F6', 'bg': '#DBEAFE'},
    'plomería':         {'emoji': '🚰', 'color': '#3B82F6', 'bg': '#DBEAFE'},
    'plomeria':         {'emoji': '🚰', 'color': '#3B82F6', 'bg': '#DBEAFE'},
    'pinturas':         {'emoji': '🎨', 'color': '#8B5CF6', 'bg': '#EDE9FE'},
    'construcción':     {'emoji': '🧱', 'color': '#D97706', 'bg': '#FEF3C7'},
    'jardinería':       {'emoji': '🪴', 'color': '#22C55E', 'bg': '#DCFCE7'},
}

def _get_cat_config(category: str) -> dict:
    key = category.lower().strip()
    for k, v in CATEGORY_CONFIG.items():
        if k in key:
            return v
    return {'emoji': '📦', 'color': '#64748B', 'bg': '#F1F5F9'}

def _image_to_base64(img_path: str) -> str:
    if not os.path.exists(img_path):
        return ""
    try:
        with open(img_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        ext = os.path.splitext(img_path)[1].lower()
        mime = "image/png"
        if ext in [".jpg", ".jpeg"]:
            mime = "image/jpeg"
        elif ext == ".webp":
            mime = "image/webp"
        return f"data:{mime};base64,{encoded}"
    except:
        return ""

def _safe_int(val: Any) -> int:
    try:
        if isinstance(val, str):
            import re
            m = re.search(r'\d+', val)
            return int(m.group()) if m else 0
        return int(val)
    except:
        return 0

def generate_inventory_html(products: List[Dict[str, Any]]) -> str:
    total_units = sum(_safe_int(p.get('cantidad_estimada', 0)) for p in products)
    
    html = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Inventario Detectado</title>
        <style>
            body {
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
                background-color: #f8fafc;
                color: #0f172a;
                margin: 0;
                padding: 40px 20px;
            }
            .container {
                max-width: 1000px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
                overflow: hidden;
            }
            .header {
                background: linear-gradient(135deg, #1e3a8a, #3b82f6);
                padding: 30px;
                color: white;
                text-align: center;
            }
            .header h1 {
                margin: 0 0 10px 0;
                font-size: 28px;
            }
            .header p {
                margin: 0;
                color: #bfdbfe;
                font-size: 14px;
            }
            .stats {
                display: flex;
                justify-content: space-around;
                background: #f1f5f9;
                padding: 15px;
                border-bottom: 1px solid #e2e8f0;
            }
            .stat-box {
                text-align: center;
            }
            .stat-value {
                font-size: 20px;
                font-weight: bold;
                color: #0f172a;
            }
            .stat-label {
                font-size: 12px;
                color: #64748b;
                text-transform: uppercase;
            }
            table {
                width: 100%;
                border-collapse: collapse;
            }
            th {
                background: #f8fafc;
                padding: 15px;
                text-align: left;
                font-size: 13px;
                color: #475569;
                text-transform: uppercase;
                border-bottom: 2px solid #e2e8f0;
            }
            td {
                padding: 15px;
                border-bottom: 1px solid #e2e8f0;
                vertical-align: middle;
            }
            tr:last-child td {
                border-bottom: none;
            }
            tr:hover {
                background-color: #f8fafc;
            }
            .img-container {
                width: 50px;
                height: 50px;
                border-radius: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 24px;
                overflow: hidden;
            }
            .img-container img {
                width: 100%;
                height: 100%;
                object-fit: cover;
            }
            .badge {
                padding: 4px 10px;
                border-radius: 9999px;
                font-size: 12px;
                font-weight: 600;
                display: inline-block;
            }
            .conf-alta { background: #dcfce7; color: #16a34a; }
            .conf-media { background: #fef3c7; color: #d97706; }
            .conf-baja { background: #fee2e2; color: #dc2626; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 Inventario Detectado por IA</h1>
                <p>Generado automáticamente desde InventarioAI + Caserita</p>
            </div>
            <div class="stats">
                <div class="stat-box">
                    <div class="stat-value">{len(products)}</div>
                    <div class="stat-label">Productos</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">{total_units}</div>
                    <div class="stat-label">Unidades</div>
                </div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Foto</th>
                        <th>Producto</th>
                        <th>Marca</th>
                        <th>Categoría</th>
                        <th>Cant.</th>
                        <th>Confianza</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    base_public = r"C:\Users\hp\.gemini\antigravity-ide\scratch\Inventario Por Imagenes\frontend\public"
    
    for idx, p in enumerate(products, 1):
        cat_config = _get_cat_config(p.get('categoria', ''))
        
        # Resolve image
        image_html = f'<div class="img-container" style="background-color: {cat_config["bg"]}; color: {cat_config["color"]};">{cat_config["emoji"]}</div>'
        
        img_url = p.get('image_url')
        if img_url:
            local_path = os.path.join(base_public, img_url.lstrip("/\\"))
            b64 = _image_to_base64(local_path)
            if b64:
                image_html = f'<div class="img-container"><img src="{b64}" alt="{p.get("nombre_producto", "")}" /></div>'
        
        conf = p.get('confianza', 'Baja')
        conf_lower = conf.lower().strip()
        conf_class = 'conf-baja'
        if conf_lower == 'alta': conf_class = 'conf-alta'
        elif conf_lower == 'media': conf_class = 'conf-media'
        
        html += f"""
                    <tr>
                        <td style="color: #94a3b8; font-size: 13px;">{idx}</td>
                        <td>{image_html}</td>
                        <td style="font-weight: 600;">{p.get('nombre_producto', '')}</td>
                        <td style="color: #64748b;">{p.get('marca', '')}</td>
                        <td>
                            <span class="badge" style="background-color: {cat_config['bg']}; color: {cat_config['color']};">
                                {p.get('categoria', '')}
                            </span>
                        </td>
                        <td style="font-weight: bold; text-align: center;">{p.get('cantidad_estimada', '0')}</td>
                        <td><span class="badge {conf_class}">{conf}</span></td>
                    </tr>
        """
        
    html += """
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """
    return html
