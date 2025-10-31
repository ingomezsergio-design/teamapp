import os
import time
from flask import Flask, render_template, jsonify, request
import gspread
from google.oauth2.service_account import Credentials
# --- NUEVA LIBRERÍA IMPORTADA ---
from googleapiclient.discovery import build

# --- Configuración de la App y Cache ---
app = Flask(__name__)
# Añadimos más permisos para que la API V4 pueda leer el formato
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]

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

# --- NUEVA FUNCIÓN PARA OBTENER DATOS CON COLORES ---
def get_sheet_data_with_colors(spreadsheet_id, sheet_name):
    """
    Usa la API de Google Sheets v4 para obtener valores Y colores de fondo.
    """
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service-account.json")
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    
    service = build('sheets', 'v4', credentials=creds)
    sheet_api = service.spreadsheets()

    # Petición a la API pidiendo explícitamente los valores y el formato de color de fondo
    result = sheet_api.get(
        spreadsheetId=spreadsheet_id,
        ranges=[sheet_name],
        includeGridData=True
    ).execute()

    grid_data = result['sheets'][0]['data'][0]
    headers = []
    rows_with_colors = []

    # Procesar la primera fila (encabezados)
    if 'rowData' in grid_data and len(grid_data['rowData']) > 0:
        header_row = grid_data['rowData'][0]
        if 'values' in header_row:
            headers = [cell.get('formattedValue', '') for cell in header_row['values']]

    # Procesar el resto de las filas
    if 'rowData' in grid_data and len(grid_data['rowData']) > 1:
        for row_data in grid_data['rowData'][1:]:
            row_list = []
            if 'values' in row_data:
                for cell in row_data['values']:
                    # Extraemos el color de la celda
                    bg_color_map = cell.get('effectiveFormat', {}).get('backgroundColor', {})
                    # Convertimos el color de formato RGBA de la API a un string hexadecimal CSS
                    hex_color = '#FFFFFF' # Blanco por defecto
                    if 'red' in bg_color_map or 'green' in bg_color_map or 'blue' in bg_color_map:
                        r = int(bg_color_map.get('red', 0) * 255)
                        g = int(bg_color_map.get('green', 0) * 255)
                        b = int(bg_color_map.get('blue', 0) * 255)
                        hex_color = f'#{r:02x}{g:02x}{b:02x}'
                    
                    row_list.append({
                        "value": cell.get('formattedValue', ''),
                        "color": hex_color
                    })
            rows_with_colors.append(row_list)

    return {"headers": headers, "rows": rows_with_colors}

# --- Rutas de la Interfaz ---
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/agentes")
def agentes():
    return render_template("agentes.html")

@app.route("/metricas-pic")
def metricas_pic():
    return render_template("metricas_pic.html")

# --- Endpoints de API existentes (sin cambios) ---
# ... (aquí van tus endpoints /api/agents/meta y /api/agents/chunk) ...

# --- MODIFICAMOS EL ENDPOINT DE MÉTRICAS PIC ---
@app.route("/api/metricas-pic/data")
def api_metricas_pic_data():
    """ Ahora llama a la nueva función que obtiene colores. """
    try:
        ss_id = os.getenv("SPREADSHEET_ID", "1Iowck5rzr8gjIZwLCQazg1eNktoW6RQ9fmGnKoPNIyE")
        data = get_sheet_data_with_colors(ss_id, 'Metricas PIC')
        return jsonify(data)
    except Exception as e:
        # Importante: imprimir el error en la consola del servidor para depuración
        print(f"Error en api_metricas_pic_data: {e}")
        return jsonify({"error": str(e)}), 500

# --- Lógica para correr la app ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=True)
