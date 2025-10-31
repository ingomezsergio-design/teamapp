import os
import time
from flask import Flask, render_template, jsonify, request
import gspread
from google.oauth2.service_account import Credentials

# --- Configuración de la App y Cache ---
app = Flask(__name__)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

sheet_cache = {
    "data": None,
    "timestamp": 0
}
CACHE_DURATION = 120

# --- Funciones de Lógica ---
def get_gspread_client():
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service-account.json")
    if not os.path.exists(creds_path):
        raise FileNotFoundError(f"No se encontró el archivo de credenciales: {creds_path}")
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return gspread.authorize(creds)

def get_sheet_snapshot():
    current_time = time.time()
    if sheet_cache["data"] and (current_time - sheet_cache["timestamp"] < CACHE_DURATION):
        return sheet_cache["data"]

    gc = get_gspread_client()
    ss_id = os.getenv("SPREADSHEET_ID", "1Iowck5rzr8gjIZwLCQazg1eNktoW6RQ9fmGnKoPNIyE")
    sh = gc.open_by_key(ss_id).worksheet("Agentes")
    
    values = sh.get_all_values()
    
    snapshot = {
        "headers": values[0] if values else [],
        "rows": values[1:] if len(values) > 1 else [],
        "version": str(current_time)
    }
    
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

# --- NUEVA RUTA para la página de Métricas PIC ---
@app.route("/metricas-pic")
def metricas_pic():
    return render_template("metricas_pic.html")

# --- Endpoints de API para la página de Agentes ---
@app.route("/api/agents/meta")
def api_agents_meta():
    try:
        snapshot = get_sheet_snapshot()
        return jsonify({
            "headers": snapshot["headers"],
            "total": len(snapshot["rows"]),
            "version": snapshot["version"]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/agents/chunk")
def api_agents_chunk():
    try:
        start = int(request.args.get('start', 0))
        size = int(request.args.get('size', 200))
        
        snapshot = get_sheet_snapshot()
        total = len(snapshot["rows"])
        end = min(total, start + size)
        
        return jsonify({
            "rows": snapshot["rows"][start:end],
            "colors": [[] for _ in range(start, end)], 
            "start": start,
            "end": end,
            "total": total,
            "version": snapshot["version"]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- NUEVO ENDPOINT DE API para Métricas PIC ---
@app.route("/api/metricas-pic/data")
def api_metricas_pic_data():
    """ Obtiene todos los datos de la hoja 'Metricas PIC'. """
    try:
        gc = get_gspread_client()
        ss_id = os.getenv("SPREADSHEET_ID", "1Iowck5rzr8gjIZwLCQazg1eNktoW6RQ9fmGnKoPNIyE")
        sh = gc.open_by_key(ss_id).worksheet('Metricas PIC')
        
        values = sh.get_all_values()
        
        headers = values[0] if values else []
        rows = values[1:] if len(values) > 1 else []
        
        return jsonify({
            "headers": headers,
            "rows": rows
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Lógica para correr la app ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=True)
