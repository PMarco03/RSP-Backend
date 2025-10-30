from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import threading
import time
from datetime import datetime, timedelta

CONFIG_PATH = "config.json"

app = Flask(__name__)
CORS(app)

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)

@app.route("/states", methods=["GET"])
def get_states():
    config = load_config()
    return jsonify(config)

@app.route("/override", methods=["POST"])
def update_state():
    data = request.get_json()
    override_state = data.get("OverrideState")
    valve_id = data.get("Id")

    config = load_config()
    for valve in config["Valves"]:
        if valve["Id"] == valve_id:
            valve["OverrideState"] = bool(override_state)
            break

    save_config(config)
    return jsonify({"status": "ok", "updated": valve_id})

@app.route("/toggleglobalstate", methods=["POST"])
def toggle_GlobalState():
    data = request.get_json()
    globalState = data.get("GlobalState")
    config = load_config()
    config["GlobalState"] = bool(globalState)
    save_config(config)
    return jsonify({"status": "ok", "GlobalState": globalState})

@app.route("/update", methods=["POST"])
def update_valves():
    data = request.get_json()
    valves_data = data.get("valves", [])
    config = load_config()

    for new_valve in valves_data:
        vid = new_valve.get("Id")
        tstart = new_valve.get("TimeStart")
        duration = new_valve.get("Duration")

        for valve in config["Valves"]:
            if valve["Id"] == vid:
                if tstart is not None:
                    valve["TimeStart"] = tstart
                if duration is not None:
                    valve["Duration"] = duration
                break

    save_config(config)
    return jsonify({"status": "ok", "updated_count": len(valves_data)})

@app.route("/status", methods=["GET"])
def get_status():
    config = load_config()
    status = {
        "GlobalState": config.get("GlobalState", False),
        "Valves": [
            {
                "Id": v["Id"],
                "State": v["State"],
                "OverrideState": v["OverrideState"]
            } for v in config["Valves"]
        ]
    }
    return jsonify(status)

def scheduler():
    while True:
        try:
            config = load_config()
            now = datetime.now()
            if(config.get("GlobalState", False) == True):
                for valve in config["Valves"]:
                    if valve.get("OverrideState",False) == valve.get("State",False):
                        try:
                            t_raw = valve.get("TimeStart", "00:00")
                            duration = int(valve.get("Duration", 0))

                            # Gestisce vari formati (HH:MM o HH:MM:SS)
                            try:
                                t_start = datetime.strptime(t_raw, "%H:%M").time()
                            except ValueError:
                                t_start = datetime.strptime(t_raw, "%H:%M:%S").time()

                            start_dt = datetime.combine(datetime.today(), t_start)
                            end_dt = start_dt + timedelta(minutes=duration)

                            if start_dt <= now <= end_dt:
                                valve["State"] = True
                                valve["OverrideState"] = True
                            else:
                                valve["State"] = False
                                valve["OverrideState"] = False

                        except Exception as e:
                            print(f"Errore nella valvola {valve.get('Id')}: {e}")
                            continue

            save_config(config)
        except Exception as e:
            print("Errore scheduler:", e)

        time.sleep(1)


if __name__ == "__main__":
    thread = threading.Thread(target=scheduler, daemon=True)
    thread.start()
    app.run(host="0.0.0.0", port=5000)
