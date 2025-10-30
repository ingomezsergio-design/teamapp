import os
from flask import Flask, render_template, jsonify, request
import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

def get_gspread_client():
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service-account.json")
    if not os.path.exists(creds_path):
        raise FileNotFoundError(
            f"No se encontró el archivo de credenciales: {creds_path}. "
            f"Definí GOOGLE_APPLICATION_CREDENTIALS o colocá service-account.json en la raíz."
        )
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return gspread.authorize(creds)

def open_sheet():
    ss_id = os.getenv("SPREADSHEET_ID", "1Iowck5rzr8gjIZwLCQazg1eNktoW6RQ9fmGnKoPNIyE")
    sheet_name = os.getenv("SHEET_NAME", "Agentes")
    gc = get_gspread_client()
    sh = gc.open_by_key(ss_id).worksheet(sheet_name)
    return sh

def fetch_agents():
    sh = open_sheet()
    values = sh.get_all_values()
    if not values:
        return []
    headers = values[0]
    rows = values[1:]
    # por compatibilidad con tu hoja: nombre en Col C (index 2)
    name_idx = 2 if len(headers) > 2 else 0
    agents = []
    for i, r in enumerate(rows, start=2):  # +2 porque 1=header, start=2 -> número de fila real
        name = (r[name_idx-1] if name_idx>0 and len(r) >= name_idx else "").strip() if name_idx>0 else (r[0].strip() if r else "")
        # Ajuste por índices: arriba calculé mal; re-calc seguro:
        if len(r) > 2:
            name = r[2].strip()
        elif len(r) > 0:
            name = r[0].strip()
        if name:
            agents.append({"name": name, "row": i})
    return agents

def fetch_row(row_number:int):
    """Devuelve headers y la fila completa (row_number es 1-based en la hoja)."""
    sh = open_sheet()
    values = sh.get_all_values()
    if not values or row_number < 2 or row_number > len(values):
        return {"headers": values[0] if values else [], "row": []}
    headers = values[0]
    row = values[row_number-1]  # convertir 1-based -> 0-based
    return {"headers": headers, "row": row}

def create_app():
    app = Flask(__name__)

    @app.route("/")
    def home():
        return render_template("home.html")

    @app.route("/agentes")
    def agentes():
        try:
            agents = fetch_agents()
        except Exception as e:
            return render_template("agentes.html", agents=[], error=str(e))
        return render_template("agentes.html", agents=agents, error=None)

    @app.route("/api/agents")
    def api_agents():
        try:
            return jsonify({"ok": True, "agents": fetch_agents()})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/api/agent")
    def api_agent():
        try:
            row = int(request.args.get("row", "0"))
        except ValueError:
            return jsonify({"ok": False, "error": "row inválido"}), 400
        try:
            data = fetch_row(row)
            return jsonify({"ok": True, **data})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    return app

app = create_app()

if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=True)
