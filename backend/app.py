import os
import io
import csv
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, send_from_directory, Response
from flask_cors import CORS
from dotenv import load_dotenv

import database

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("WeatherAlertApp")

# Setup Flask application
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
TEMPLATE_DIR = os.path.join(FRONTEND_DIR, "templates")
STATIC_DIR = os.path.join(FRONTEND_DIR, "static")

app = Flask(
    __name__,
    template_folder=TEMPLATE_DIR,
    static_folder=STATIC_DIR,
    static_url_path="/static"
)
CORS(app)

API_KEY = os.getenv("API_KEY", "WEATHER_FARM_KEY_2026")
DEVICE_OFFLINE_THRESHOLD_SECONDS = 60  # Marked offline if no data for 60 seconds


def classify_rain_level(rain_value, rain_detected):
    """
    Classify rainfall level:
    - No Rain
    - Light Rain (Low)
    - Medium Rain (Moderate / Medium)
    - Heavy Rain (High / Heavy)
    """
    if not rain_detected:
        return "No Rain"
    
    try:
        val = float(rain_value or 0)
    except (ValueError, TypeError):
        val = 0.0

    # If raw ADC > 100 on ESP32 (0-4095)
    if val > 100:
        val = max(0, min(100, int((4095 - val) / 4095 * 100)))

    if val > 70:
        return "Heavy Rain"
    elif val >= 30:
        return "Medium Rain"
    elif val > 1:
        return "Light Rain"
    else:
        # Digital rain sensor pin LOW (0): water actively detected on plate
        return "Heavy Rain"


def evaluate_threshold_alerts(reading):
    """
    Check reading against configured thresholds and create alerts.
    Includes anti-spam cooldown so identical alerts aren't generated every 5 seconds.
    """
    triggered_alerts = []
    
    # Fetch active thresholds
    thresholds = database.query_all("SELECT * FROM alert_thresholds;")
    th_dict = {t["parameter_key"]: t for t in thresholds}
    
    temp = float(reading["temperature"])
    hum = float(reading["humidity"])
    rain = float(reading.get("rain_value", 0))
    rain_detected = bool(reading.get("rain_detected", False))
    
    alerts_to_check = []
    
    # 1. Temperature checks
    t_rule = th_dict.get("temperature")
    if t_rule:
        if t_rule.get("max_value") is not None and temp > float(t_rule["max_value"]):
            alerts_to_check.append({
                "alert_type": "HEAT_STRESS",
                "severity": "DANGER" if temp >= (float(t_rule["max_value"]) + 4) else "WARNING",
                "message": f"High Field Temperature Warning: {temp:.1f}°C (Exceeds safe limit of {t_rule['max_value']}°C).",
                "agricultural_advice": "High risk of plant heat stress and soil moisture depletion. Start drip or sprinkler irrigation; deploy shade nets over nurseries.",
                "sensor_value": temp,
                "threshold_value": float(t_rule["max_value"])
            })
        elif t_rule.get("min_value") is not None and temp < float(t_rule["min_value"]):
            alerts_to_check.append({
                "alert_type": "FROST_RISK",
                "severity": "DANGER" if temp <= 4.0 else "WARNING",
                "message": f"Cold & Frost Hazard Warning: {temp:.1f}°C (Below minimum limit of {t_rule['min_value']}°C).",
                "agricultural_advice": "Frost risk for sensitive crops and saplings. Cover nursery beds with plastic mulch or activate protective thermal irrigation.",
                "sensor_value": temp,
                "threshold_value": float(t_rule["min_value"])
            })

    # 2. Humidity checks
    h_rule = th_dict.get("humidity")
    if h_rule:
        if h_rule.get("max_value") is not None and hum > float(h_rule["max_value"]):
            alerts_to_check.append({
                "alert_type": "HIGH_HUMIDITY",
                "severity": "WARNING",
                "message": f"Excessive Humidity Warning: {hum:.1f}% (Exceeds optimal limit of {h_rule['max_value']}%).",
                "agricultural_advice": "High atmospheric humidity creates favorable conditions for fungal blight, mildew, and pest infestation. Ensure field airflow and postpone spraying agrochemicals.",
                "sensor_value": hum,
                "threshold_value": float(h_rule["max_value"])
            })
        elif h_rule.get("min_value") is not None and hum < float(h_rule["min_value"]):
            alerts_to_check.append({
                "alert_type": "LOW_HUMIDITY",
                "severity": "INFO",
                "message": f"Low Air Humidity Advisory: {hum:.1f}% (Below threshold of {h_rule['min_value']}%).",
                "agricultural_advice": "Dry conditions accelerate crop transpiration. Monitor soil moisture levels closely.",
                "sensor_value": hum,
                "threshold_value": float(h_rule["min_value"])
            })

    # 3. Rain checks: Trigger alert whenever water is detected on the sensor plate
    if rain_detected:
        alerts_to_check.append({
            "alert_type": "RAIN_DETECTED",
            "severity": "WARNING",
            "message": "Rainfall detected on the field sensor plate.",
            "agricultural_advice": "Active rainfall detected on the field sensor. Suspend scheduled irrigation to conserve water and prevent soil saturation.",
            "sensor_value": rain,
            "threshold_value": 0.0
        })

    # Deduplicate against recent alerts (last 10 minutes)
    for alert in alerts_to_check:
        # Check if identical alert exists in last 10 minutes
        recent_cutoff = (datetime.now() - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
        existing = database.query_one(
            """
            SELECT id FROM weather_alerts 
            WHERE alert_type = %s 
              AND is_resolved = 0 
              AND created_at >= %s
            ORDER BY id DESC LIMIT 1;
            """,
            (alert["alert_type"], recent_cutoff)
        )
        if not existing:
            alert_id = database.execute_commit(
                """
                INSERT INTO weather_alerts 
                (alert_type, severity, message, agricultural_advice, sensor_value, threshold_value, is_resolved)
                VALUES (%s, %s, %s, %s, %s, %s, 0);
                """,
                (
                    alert["alert_type"],
                    alert["severity"],
                    alert["message"],
                    alert["agricultural_advice"],
                    alert["sensor_value"],
                    alert["threshold_value"]
                )
            )
            alert["id"] = alert_id
            triggered_alerts.append(alert)
            logger.info(f"Triggered Alert [{alert['alert_type']}]: {alert['message']}")

    return triggered_alerts


# ==========================================
# Frontend Routes
# ==========================================

@app.route("/")
def index():
    """Serve the main farmer weather monitoring dashboard."""
    return render_template("index.html")


@app.route("/health")
def health_check():
    """Health check endpoint for Docker container monitoring."""
    db_status = "connected"
    try:
        database.query_one("SELECT 1;")
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return jsonify({
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "database_mode": database.get_db_mode(),
        "timestamp": datetime.now().isoformat()
    }), 200 if db_status == "connected" else 500


# ==========================================
# REST API Endpoints
# ==========================================

@app.route("/api/sensor-data", methods=["POST"])
def receive_sensor_data():
    """
    Receives telemetry from ESP32 microcontroller or test client.
    Expects JSON:
    {
        "device_id": "ESP32_FARM_01",
        "temperature": 27.8,
        "humidity": 65.2,
        "rain_value": 45,       // Percentage (0-100) or analog ADC (0-4095)
        "rain_detected": true   // or 1/0
    }
    """
    # Optional API key verification (allows flexible header or query/body key)
    header_key = request.headers.get("X-API-KEY")
    req_data = request.get_json(silent=True)
    
    if not req_data:
        return jsonify({"status": "error", "message": "Invalid JSON payload"}), 400

    # API key check if supplied
    provided_key = header_key or req_data.get("api_key")
    if API_KEY and provided_key and provided_key != API_KEY:
        return jsonify({"status": "error", "message": "Unauthorized: Invalid API Key"}), 401

    device_id = str(req_data.get("device_id", "ESP32_FARM_01")).strip()
    
    try:
        temperature = float(req_data.get("temperature"))
        humidity = float(req_data.get("humidity"))
        raw_rain = float(req_data.get("rain_value", 0))
    except (TypeError, ValueError) as e:
        return jsonify({
            "status": "error", 
            "message": f"Malformed sensor reading values: {str(e)}"
        }), 422

    # Robust rain detection logic:
    # 1. Inspect explicit rain_detected parameter (boolean, number, or string)
    is_rain = False
    rd_raw = req_data.get("rain_detected")
    if rd_raw is not None:
        if isinstance(rd_raw, bool):
            is_rain = rd_raw
        elif isinstance(rd_raw, (int, float)):
            is_rain = bool(rd_raw == 1)
        elif isinstance(rd_raw, str):
            is_rain = rd_raw.strip().lower() in ("true", "1", "yes")

    # 2. Inspect rain_status text parameter ("Heavy Rain", "Medium Rain", "Light Rain", "Water Detected", "No Rain")
    rs_raw = req_data.get("rain_status")
    rain_level = None
    if rs_raw:
        status_clean = str(rs_raw).strip().lower()
        if "no water" in status_clean or "no rain" in status_clean or "no_rain" in status_clean or "dry" in status_clean:
            is_rain = False
            rain_level = "No Rain"
        elif "heavy" in status_clean or "high" in status_clean:
            is_rain = True
            rain_level = "Heavy Rain"
        elif "medium" in status_clean or "moderate" in status_clean:
            is_rain = True
            rain_level = "Medium Rain"
        elif "light" in status_clean or "low" in status_clean:
            is_rain = True
            rain_level = "Light Rain"
        elif "water" in status_clean or "rain" in status_clean:
            is_rain = True

    # 3. Fallback for ESP32 active-LOW digital rain sensor (0 = LOW = water detected, 1 = HIGH = dry)
    if rd_raw is None and rs_raw is None:
        if raw_rain == 0:
            is_rain = True
        elif raw_rain == 1:
            is_rain = False
        elif raw_rain > 100:
            # ADC reading where lower values indicate moisture
            is_rain = raw_rain < 3500

    rain_detected = is_rain
    if not is_rain:
        rain_status = str(rs_raw) if rs_raw else "No Rain"
        rain_level = "No Rain"
    else:
        if not rain_level:
            rain_level = classify_rain_level(raw_rain, is_rain)
        rain_status = str(rs_raw) if rs_raw else rain_level

    stored_rain_value = int(raw_rain)

    # Physical boundary validation
    if not (-20.0 <= temperature <= 75.0):
        return jsonify({"status": "error", "message": "Temperature reading out of plausible bounds (-20 to 75°C)"}), 422
    if not (0.0 <= humidity <= 100.0):
        return jsonify({"status": "error", "message": "Humidity reading out of bounds (0 to 100%)"}), 422

    client_ip = request.remote_addr

    # Store reading
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    reading_id = database.execute_commit(
        """
        INSERT INTO sensor_readings 
        (device_id, temperature, humidity, rain_value, rain_detected, rain_status, rain_level, recorded_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """ if database.get_db_mode() == "mysql" else """
        INSERT INTO sensor_readings 
        (device_id, temperature, humidity, rain_value, rain_detected, rain_status, rain_level, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (device_id, temperature, humidity, stored_rain_value, 1 if rain_detected else 0, rain_status, rain_level, now_str)
    )

    # Update or insert device status
    database.execute_commit(
        """
        INSERT INTO devices (device_id, device_name, ip_address, status, last_seen)
        VALUES (%s, %s, %s, 'ONLINE', %s)
        ON DUPLICATE KEY UPDATE 
            ip_address=VALUES(ip_address), 
            status='ONLINE', 
            last_seen=VALUES(last_seen);
        """ if database.get_db_mode() == "mysql" else """
        INSERT INTO devices (device_id, device_name, ip_address, status, last_seen)
        VALUES (?, 'ESP32 Farm Node', ?, 'ONLINE', ?)
        ON CONFLICT(device_id) DO UPDATE SET 
            ip_address=excluded.ip_address, 
            status='ONLINE', 
            last_seen=excluded.last_seen;
        """,
        (device_id, "ESP32 Farm Node", client_ip, now_str) if database.get_db_mode() == "mysql" else (device_id, client_ip, now_str)
    )

    # Check alert rules
    reading_record = {
        "device_id": device_id,
        "temperature": temperature,
        "humidity": humidity,
        "rain_value": stored_rain_value,
        "rain_detected": rain_detected
    }
    alerts_triggered = evaluate_threshold_alerts(reading_record)

    logger.info(f"Recorded Reading #{reading_id} from [{device_id}]: Temp={temperature}°C, Hum={humidity}%, Rain={rain_status} (raw={stored_rain_value})")

    return jsonify({
        "status": "success",
        "message": "Sensor reading recorded successfully",
        "reading_id": reading_id,
        "data": {
            "device_id": device_id,
            "temperature": temperature,
            "humidity": humidity,
            "rain_value": stored_rain_value,
            "rain_detected": rain_detected,
            "rain_status": rain_status,
            "rain_level": rain_level,
            "recorded_at": now_str
        },
        "alerts_triggered": alerts_triggered
    }), 201


@app.route("/api/sensor-data/latest", methods=["GET"])
def get_latest_sensor_data():
    """Return the most recent sensor reading and current system advisory."""
    reading = database.query_one(
        """
        SELECT id, device_id, temperature, humidity, rain_value, rain_detected, rain_status, rain_level, recorded_at
        FROM sensor_readings
        ORDER BY id DESC
        LIMIT 1;
        """
    )
    
    device = database.query_one(
        """
        SELECT device_id, device_name, ip_address, last_seen, status
        FROM devices
        ORDER BY last_seen DESC
        LIMIT 1;
        """
    )

    # Determine real-time connectivity status
    is_online = False
    seconds_ago = None
    if device and device.get("last_seen"):
        last_seen = device["last_seen"]
        if isinstance(last_seen, str):
            try:
                last_seen = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
            except Exception:
                last_seen = datetime.strptime(str(last_seen)[:19], "%Y-%m-%d %H:%M:%S")
        seconds_ago = int((datetime.now() - last_seen).total_seconds())
        is_online = seconds_ago <= DEVICE_OFFLINE_THRESHOLD_SECONDS

    # Count active unresolved alerts
    active_alerts_count = database.query_one(
        "SELECT COUNT(*) as count FROM weather_alerts WHERE is_resolved = 0;"
    )
    count = active_alerts_count["count"] if active_alerts_count else 0

    # Agricultural advisory algorithm based on current weather conditions
    advisory = "Normal field conditions. Continue standard agricultural practices."
    if reading:
        if isinstance(reading.get("recorded_at"), datetime):
            reading["recorded_at"] = reading["recorded_at"].strftime("%Y-%m-%d %H:%M:%S")

        temp = float(reading["temperature"])
        hum = float(reading["humidity"])

        # Determine rain detection status cleanly
        raw_det = reading.get("rain_detected")
        is_det = False
        if raw_det is True or raw_det == 1 or str(raw_det).lower() in ("true", "1"):
            is_det = True
        elif reading.get("rain_status"):
            st = str(reading.get("rain_status")).lower()
            if "no water" in st or "no rain" in st or "no_rain" in st or "dry" in st:
                is_det = False
            elif "water" in st or "rain" in st or "heavy" in st or "medium" in st or "light" in st:
                is_det = True
        elif reading.get("rain_value") == 0 and raw_det is None:
            is_det = True

        reading["rain_detected"] = is_det
        curr_status = reading.get("rain_status") or reading.get("rain_level")
        if not is_det:
            reading["rain_status"] = str(curr_status) if curr_status else "No Rain"
            reading["rain_level"] = "No Rain"
        else:
            lvl = classify_rain_level(reading.get("rain_value"), is_det)
            reading["rain_level"] = lvl
            reading["rain_status"] = str(curr_status) if curr_status else lvl
        
        if is_det:
            advisory = f"{reading['rain_status']} in progress. Pause scheduled irrigation systems to conserve water."
        elif temp > 33.0:
            advisory = "High heat conditions. Irrigate during early morning or evening hours to minimize evaporation losses."
        elif temp < 12.0:
            advisory = "Cool temperature warning. Sensitive crops should be monitored for cold injury or chilling stress."
        elif hum > 80.0:
            advisory = "High ambient humidity. Inspect foliage for fungal infections (powdery mildew/leaf rust). Delay foliar spray."

    return jsonify({
        "status": "success",
        "reading": reading,
        "device": {
            "device_id": device["device_id"] if device else "ESP32_FARM_01",
            "is_online": is_online,
            "seconds_since_last_seen": seconds_ago,
            "ip_address": device.get("ip_address") if device else None
        },
        "active_alerts_count": count,
        "agricultural_advisory": advisory,
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


@app.route("/api/sensor-data/history", methods=["GET"])
def get_sensor_history():
    """
    Retrieve historical sensor readings.
    Query parameters:
    - limit: maximum number of records (default 50, max 2000)
    - range: '1h', '6h', '24h', '7d', 'all'
    - start_date: YYYY-MM-DD
    - end_date: YYYY-MM-DD
    """
    raw_limit = request.args.get("limit")
    time_range = request.args.get("range")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    default_limit = 100 if time_range else 50
    limit = min(int(raw_limit) if raw_limit else default_limit, 2000)

    query = "SELECT id, device_id, temperature, humidity, rain_value, rain_detected, rain_status, rain_level, recorded_at FROM sensor_readings"
    params = []
    conditions = []

    now = datetime.now()
    if time_range == "1h":
        start_time = (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        conditions.append("recorded_at >= %s")
        params.append(start_time)
        limit = max(limit, 500)
    elif time_range == "6h":
        start_time = (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")
        conditions.append("recorded_at >= %s")
        params.append(start_time)
        limit = max(limit, 1000)
    elif time_range == "24h":
        start_time = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        conditions.append("recorded_at >= %s")
        params.append(start_time)
        limit = max(limit, 1500)
    elif time_range == "7d":
        start_time = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        conditions.append("recorded_at >= %s")
        params.append(start_time)
        limit = max(limit, 2000)

    if start_date:
        conditions.append("recorded_at >= %s")
        params.append(f"{start_date} 00:00:00")
    if end_date:
        conditions.append("recorded_at <= %s")
        params.append(f"{end_date} 23:59:59")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY id DESC LIMIT %s;"
    params.append(limit)

    readings = database.query_all(query, tuple(params))
    
    # Format fields
    for r in readings:
        if isinstance(r.get("recorded_at"), datetime):
            r["recorded_at"] = r["recorded_at"].strftime("%Y-%m-%d %H:%M:%S")
        raw_det = r.get("rain_detected")
        is_det = False
        if raw_det is True or raw_det == 1 or str(raw_det).lower() in ("true", "1"):
            is_det = True
        elif r.get("rain_status"):
            st = str(r.get("rain_status")).lower()
            if "no water" in st or "no rain" in st or "no_rain" in st:
                is_det = False
            elif "water" in st or "rain" in st:
                is_det = True
        elif r.get("rain_value") == 0 and raw_det is None:
            is_det = True

        r["rain_detected"] = is_det
        curr_status = r.get("rain_status") or r.get("rain_level")
        if not is_det:
            r["rain_status"] = str(curr_status) if curr_status else "No Rain"
            r["rain_level"] = "No Rain"
        else:
            lvl = classify_rain_level(r.get("rain_value"), is_det)
            r["rain_level"] = lvl
            r["rain_status"] = str(curr_status) if curr_status else lvl

    # Return chronologically ascending for charts
    readings.reverse()

    return jsonify({
        "status": "success",
        "count": len(readings),
        "range": time_range or "default",
        "readings": readings
    })


@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    """Retrieve weather alerts with optional filter for status (active, resolved, all)."""
    filter_status = request.args.get("status", "all").lower()
    limit = min(int(request.args.get("limit", 20)), 100)

    if filter_status == "active":
        query = "SELECT * FROM weather_alerts WHERE is_resolved = 0 ORDER BY id DESC LIMIT %s;"
        alerts = database.query_all(query, (limit,))
    elif filter_status == "resolved":
        query = "SELECT * FROM weather_alerts WHERE is_resolved = 1 ORDER BY id DESC LIMIT %s;"
        alerts = database.query_all(query, (limit,))
    else:
        query = "SELECT * FROM weather_alerts ORDER BY id DESC LIMIT %s;"
        alerts = database.query_all(query, (limit,))

    return jsonify({
        "status": "success",
        "alerts": alerts
    })


@app.route("/api/alerts/<int:alert_id>/resolve", methods=["POST"])
def resolve_alert(alert_id):
    """Mark a specific alert as resolved."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    database.execute_commit(
        "UPDATE weather_alerts SET is_resolved = 1, resolved_at = %s WHERE id = %s;",
        (now_str, alert_id)
    )
    return jsonify({"status": "success", "message": f"Alert #{alert_id} resolved"})


@app.route("/api/alerts/resolve-all", methods=["POST"])
def resolve_all_alerts():
    """Resolve all currently active alerts."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    database.execute_commit(
        "UPDATE weather_alerts SET is_resolved = 1, resolved_at = %s WHERE is_resolved = 0;",
        (now_str,)
    )
    return jsonify({"status": "success", "message": "All active alerts resolved"})


@app.route("/api/thresholds", methods=["GET"])
def get_thresholds():
    """Retrieve configured safety thresholds."""
    thresholds = database.query_all("SELECT * FROM alert_thresholds ORDER BY id ASC;")
    return jsonify({
        "status": "success",
        "thresholds": thresholds
    })


@app.route("/api/thresholds", methods=["POST", "PUT"])
def update_thresholds():
    """
    Update threshold bounds.
    Body format:
    {
        "temperature": {"min": 12.0, "max": 36.0},
        "humidity": {"min": 25.0, "max": 80.0},
        "rain": {"max": 50.0}
    }
    """
    data = request.get_json(silent=True) or {}
    updated = []

    for key, bounds in data.items():
        min_val = bounds.get("min")
        max_val = bounds.get("max")
        database.execute_commit(
            """
            UPDATE alert_thresholds 
            SET min_value = %s, max_value = %s, updated_at = CURRENT_TIMESTAMP
            WHERE parameter_key = %s;
            """,
            (min_val, max_val, key)
        )
        updated.append(key)

    logger.info(f"Updated threshold configuration for: {updated}")
    return jsonify({
        "status": "success",
        "message": f"Updated thresholds for {', '.join(updated)}",
        "updated": updated
    })


@app.route("/api/device/status", methods=["GET"])
def get_device_status():
    """Device health check & heartbeat info for ESP32."""
    device = database.query_one(
        "SELECT device_id, device_name, ip_address, last_seen, status FROM devices ORDER BY last_seen DESC LIMIT 1;"
    )
    if not device:
        return jsonify({
            "status": "success",
            "is_online": False,
            "message": "No registered ESP32 devices found"
        })

    last_seen = device["last_seen"]
    if isinstance(last_seen, str):
        try:
            last_seen = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
        except Exception:
            last_seen = datetime.strptime(str(last_seen)[:19], "%Y-%m-%d %H:%M:%S")
    
    diff_sec = int((datetime.now() - last_seen).total_seconds())
    is_online = diff_sec <= DEVICE_OFFLINE_THRESHOLD_SECONDS

    return jsonify({
        "status": "success",
        "device_id": device["device_id"],
        "device_name": device["device_name"],
        "ip_address": device["ip_address"],
        "last_seen": str(device["last_seen"]),
        "seconds_ago": diff_sec,
        "is_online": is_online,
        "connection_state": "CONNECTED" if is_online else "DISCONNECTED"
    })


@app.route("/api/sensor-data/simulate", methods=["POST"])
def simulate_sensor_data():
    """
    Simulation endpoint for project evaluation, demonstration, and viva.
    Generates realistic weather events:
    - 'normal'
    - 'heatwave'
    - 'frost'
    - 'heavy_rain'
    - 'humid'
    """
    import random
    req_data = request.get_json(silent=True) or {}
    scenario = req_data.get("scenario", "normal")

    if scenario == "heatwave":
        temp = round(random.uniform(36.5, 42.0), 1)
        hum = round(random.uniform(28.0, 45.0), 1)
        rain_val = 0
        rain_det = False
    elif scenario == "frost":
        temp = round(random.uniform(4.0, 9.5), 1)
        hum = round(random.uniform(60.0, 75.0), 1)
        rain_val = 0
        rain_det = False
    elif scenario == "heavy_rain":
        temp = round(random.uniform(22.0, 25.5), 1)
        hum = round(random.uniform(85.0, 95.0), 1)
        rain_val = random.randint(75, 95)
        rain_det = True
    elif scenario == "humid":
        temp = round(random.uniform(29.0, 33.0), 1)
        hum = round(random.uniform(88.0, 96.0), 1)
        rain_val = random.randint(15, 30)
        rain_det = True
    else:  # normal
        temp = round(random.uniform(24.0, 29.0), 1)
        hum = round(random.uniform(50.0, 68.0), 1)
        rain_val = random.randint(0, 10)
        rain_det = False

    simulated_reading = {
        "device_id": "ESP32_FARM_01",
        "temperature": temp,
        "humidity": hum,
        "rain_value": rain_val,
        "rain_detected": rain_det
    }

    # Pass through standard ingestion logic
    with app.test_request_context(
        "/api/sensor-data", 
        method="POST", 
        json=simulated_reading
    ):
        return receive_sensor_data()


@app.route("/api/export/csv")
def export_csv():
    """Export historical sensor readings as downloadable CSV file."""
    readings = database.query_all(
        "SELECT id, device_id, temperature, humidity, rain_value, rain_detected, rain_status, rain_level, recorded_at FROM sensor_readings ORDER BY id DESC LIMIT 1000;"
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Device ID", "Temperature (°C)", "Humidity (%)", "Rain Sensor Value", "Rain Detected", "Rain Status", "Timestamp"])

    for r in readings:
        writer.writerow([
            r["id"],
            r["device_id"],
            r["temperature"],
            r["humidity"],
            r["rain_value"],
            "YES" if r.get("rain_detected") else "NO",
            r.get("rain_status") or r.get("rain_level") or ("Rain Detected" if r.get("rain_detected") else "No Rain"),
            r["recorded_at"]
        ])

    output.seek(0)
    filename = f"weather_readings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# Initialize DB upon module load
try:
    database.init_db()
    logger.info("Database initialized successfully.")
except Exception as e:
    logger.error(f"Database initialization warning: {e}")


if __name__ == "__main__":
    port = int(os.getenv("BACKEND_PORT", 5000))
    debug_mode = os.getenv("FLASK_DEBUG", "0") in ("1", "true", "True")
    logger.info(f"Starting Smart Weather Backend server on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
