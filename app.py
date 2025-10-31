import os
import time
from flask import Flask, render_template, jsonify, request
import gspread
from google.oauth2.service_account import Credentials

# --- Configuración de la App y Cache ---
app = Flask(__name__)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Cache simple en memoria para los datos de la hoja
sheet_cache = {
    "data": None,
    "timestamp": 0
}
CACHE_DURATION = 120  # 2 minutos, igual que en tu GAS

# --- Funciones de Lógica ---
def get_gspread_client():
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service-account.json")
    if not os.path.exists(creds_path):
        raise FileNotFoundError(f"No se encontró el archivo de credenciales: {creds_path}")
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return gspread.authorize(creds)

def get_sheet_snapshot():
    """
    Obtiene los datos de la hoja, usando un cache para mejorar el rendimiento.
    Esto reemplaza la función getSnapshot_() de tu Code.gs.
    """
    current_time = time.time()
    # Si el cache es válido (menos de 2 minutos), lo usamos
    if sheet_cache["data"] and (current_time - sheet_cache["timestamp"] < CACHE_DURATION):
        return sheet_cache["data"]

    # Si no, vamos a la hoja de cálculo
    gc = get_gspread_client()
    ss_id = os.getenv("SPREADSHEET_ID", "1Iowck5rzr8gjIZwLCQazg1eNktoW6RQ9fmGnKoPNIyE")
    sheet_name = os.getenv("SHEET_NAME", "Agentes")
    sh = gc.open_by_key(ss_id).worksheet(sheet_name)
    
    values = sh.get_all_values()
    
    headers = values[0] if values else []
    rows = values[1:] if len(values) > 1 else []
    
    snapshot = {
        "headers": headers,
        "rows": rows,
        "version": str(current_time) # Usamos el timestamp como versión
    }
    
    # Actualizamos el cache
    sheet_cache["data"] = snapshot
    sheet_cache["timestamp"] = current_time
    
    return snapshot

# --- Rutas de la Interfaz ---
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/agentes")
def agentes():
    return render_template("agentes.html")

# --- NUEVOS ENDPOINTS DE API ---
# Reemplaza la necesidad de Code.gs

@app.route("/api/agents/meta")
def api_agents_meta():
    """ Devuelve los metadatos de la hoja. Reemplaza getSheetMeta(). """
    try:
        snapshot = get_sheet_snapshot()
        meta = {
            "headers": snapshot["headers"],
            "total": len(snapshot["rows"]),
            "version": snapshot["version"]
        }
        return jsonify(meta)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/agents/chunk")
def api_agents_chunk():
    """ Devuelve un "trozo" de filas. Reemplaza getRowsChunk(). """
    try:
        start = int(request.args.get('start', 0))
        size = int(request.args.get('size', 200))
        
        snapshot = get_sheet_snapshot()
        total = len(snapshot["rows"])
        end = min(total, start + size)
        
        chunk = {
            "rows": snapshot["rows"][start:end],
            # NOTA: No podemos obtener colores fácilmente con gspread, así que devolvemos un array vacío.
            "colors": [[] for _ in range(start, end)], 
            "start": start,
            "end": end,
            "total": total,
            "version": snapshot["version"]
        }
        return jsonify(chunk)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Lógica para correr la app ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=True)
