import os
import time
from flask import Flask, render_template, jsonify, request
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# --- Configuración de la App ---
app = Flask(__name__)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "1Iowck5rzr8gjIZwLCQazg1eNktoW6RQ9fmGnKoPNIyE")

# --- Cache en memoria para los datos ---
cache = {}
CACHE_DURATION = 120  # 2 minutos

# --- Función Unificada para Leer Datos de Google Sheets ---
def get_sheet_data(sheet_name):
    current_time = time.time()
    cache_key = f"sheet_{sheet_name}"

    if cache_key in cache and (current_time - cache[cache_key]["timestamp"] < CACHE_DURATION):
        return cache[cache_key]["data"]

    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service-account.json")
    if not os.path.exists(creds_path):
        raise FileNotFoundError(f"No se encontró el archivo de credenciales: {creds_path}")
    
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    sheet_api = service.spreadsheets()

    result = sheet_api.get(
        spreadsheetId=SPREADSHEET_ID,
        ranges=[sheet_name],
        includeGridData=True
    ).execute()

    if not result['sheets'][0].get('data'):
        empty_snapshot = {"headers": [], "rows": [], "rows_with_colors": [], "version": str(current_time)}
        cache[cache_key] = {"data": empty_snapshot, "timestamp": current_time}
        return empty_snapshot

    grid_data = result['sheets'][0]['data'][0]
    headers = []
    rows = []
    rows_with_colors = []

    if 'rowData' in grid_data:
        if len(grid_data['rowData']) > 0:
            header_row_data = grid_data['rowData'][0].get('values', [])
            headers = [cell.get('formattedValue', '') for cell in header_row_data]

        if len(grid_data['rowData']) > 1:
            for row_data in grid_data['rowData'][1:]:
                row_values = row_data.get('values', [])
                
                if not any(cell.get('formattedValue', '').strip() for cell in row_values):
                    continue

                values_list = []
                colors_list = []
                
                # Rellenar celdas faltantes para que coincida con el número de encabezados
                full_row_cells = row_values + [{}] * (len(headers) - len(row_values))

                for cell in full_row_cells:
                    values_list.append(cell.get('formattedValue', ''))
                    
                    bg_color_map = cell.get('effectiveFormat', {}).get('backgroundColor', {})
                    r = int(bg_color_map.get('red', 1) * 255)
                    g = int(bg_color_map.get('green', 1) * 255)
                    b = int(bg_color_map.get('blue', 1) * 255)
                    colors_list.append(f'#{r:02x}{g:02x}{b:02x}')

                rows.append(values_list)
                rows_with_colors.append([{"value": v, "color": c} for v, c in zip(values_list, colors_list)])

    snapshot = { "headers": headers, "rows": rows, "rows_with_colors": rows_with_colors, "version": str(current_time) }
    cache[cache_key] = {"data": snapshot, "timestamp": current_time}
    return snapshot

# --- Rutas de la Interfaz ---
@app.route("/")
def home(): return render_template("home.html")
@app.route("/agentes")
def agentes(): return render_template("agentes.html")
@app.route("/metricas-pic")
def metricas_pic(): return render_template("metricas_pic.html")
@app.route("/matriz-noviembre")
def matriz_noviembre(): return render_template("matriz_noviembre.html")

# --- Endpoints de API ---
@app.route("/api/agents/meta")
def api_agents_meta():
    data = get_sheet_data("Agentes")
    return jsonify({"headers": data["headers"], "total": len(data["rows"])})

@app.route("/api/agents/chunk")
def api_agents_chunk():
    start, size = int(request.args.get('start', 0)), int(request.args.get('size', 200))
    data = get_sheet_data("Agentes")
    total = len(data["rows"])
    end = min(total, start + size)
    return jsonify({"rows": data["rows"][start:end], "start": start, "end": end, "total": total})

@app.route("/api/metricas-pic/data")
def api_metricas_pic_data():
    data = get_sheet_data("Metricas PIC")
    return jsonify({"headers": data["headers"], "rows": data["rows_with_colors"]})

# --- ENDPOINT CORREGIDO ---
@app.route("/api/matriz-noviembre/data")
def api_matriz_noviembre_data():
    try:
        data = get_sheet_data("MES11")
        # Ahora enviamos la misma estructura que en Metricas PIC para mayor consistencia
        return jsonify({"headers": data["headers"], "rows": data["rows_with_colors"]})
    except Exception as e:
        print(f"Error en api_matriz_noviembre_data: {e}")
        return jsonify({"error": str(e)}), 500

# --- Lógica para correr la app ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=True)
