from flask import Flask, request, jsonify, render_template, make_response
import sqlite3
import os
import requests

app = Flask(__name__)

DB_PATH = "ubicaciones.db"
GEOLOCATION_API_KEY = os.getenv("GEOLOCATION_API_KEY", "API_KEY_NO_CONFIGURADA")

def crear_db():
    if not os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""CREATE TABLE ubicaciones (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        lat REAL,
                        lng REAL,
                        accuracy REAL)""")
        conn.commit()
        conn.close()

crear_db()

@app.route('/')
def index():
    maps_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    return render_template('mapa.html', GOOGLE_MAPS_API_KEY=maps_key)

@app.route('/ubicacion', methods=['POST'])
def recibir_ubicacion():
    data = request.json
    lat = data.get('lat')
    lng = data.get('lng')
    accuracy = data.get('accuracy', 0)

    if lat is None or lng is None:
        wifi_data = data.get('wifiAccessPoints')
        if wifi_data:
            geolocation_url = f"https://www.googleapis.com/geolocation/v1/geolocate?key={GEOLOCATION_API_KEY}"
            try:
                response = requests.post(geolocation_url, json={"wifiAccessPoints": wifi_data})
                if response.status_code == 200:
                    location = response.json()['location']
                    lat = location['lat']
                    lng = location['lng']
                    accuracy = response.json().get('accuracy', 0)

                    if accuracy > 40:
                        print(">>> Ubicación descartada por baja precisión (WPS):", accuracy)
                        return jsonify({
                            "status": "descartado",
                            "reason": "accuracy_wps_baja",
                            "accuracy": accuracy
                        }), 200
                else:
                    return jsonify({"error": "No se pudo obtener ubicación WPS"}), 400
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        else:
            return jsonify({"error": "No se recibieron coordenadas ni datos WPS"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT lat, lng FROM ubicaciones ORDER BY id DESC LIMIT 1")
    ultima = c.fetchone()

    if not ultima or (ultima[0] != lat or ultima[1] != lng):
        c.execute("INSERT INTO ubicaciones (lat, lng, accuracy) VALUES (?, ?, ?)", (lat, lng, accuracy))
        conn.commit()
    conn.close()

    return jsonify({"status": "guardado", "lat": lat, "lng": lng}), 200

@app.route('/ubicaciones', methods=['GET'])
def enviar_ubicaciones():
    client_timestamp = request.args.get('since', default=0, type=int)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT MAX(id) FROM ubicaciones")
    ultima_id = c.fetchone()[0] or 0

    if ultima_id == client_timestamp:
        conn.close()
        return make_response('', 204)

    c.execute("SELECT id, lat, lng FROM ubicaciones WHERE id > ?", (client_timestamp,))
    ubicaciones = [{"id": row[0], "lat": row[1], "lng": row[2]} for row in c.fetchall()]
    conn.close()

    return jsonify({
        "timestamp": ultima_id,
        "ubicaciones": ubicaciones
    })

@app.route('/limpiar', methods=['POST'])
def limpiar_datos():
    print(">>> Datos eliminados al cerrar la página")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM ubicaciones")
    conn.commit()
    conn.close()
    return jsonify({"status": "limpiado"})

if __name__ == '__main__':
    app.run(debug=False)
