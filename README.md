# Smart Weather Alert System for Farmers Using ESP32 and IoT

**Academic Project (MCA / B.Tech / M.Sc Computer Science & IoT)**  
**Domain:** Internet of Things (IoT), Cloud Computing, Full-Stack Web Development, Precision Agriculture  

---

## 1. Project Overview

The **Smart Weather Alert System for Farmers** is an end-to-end IoT solution that monitors microclimatic environmental parameters in agricultural fields and greenhouse environments. 

Field sensors measure **ambient temperature**, **relative humidity**, and **rainfall precipitation**. An **ESP32 microcontroller** processes these readings and transmits them over Wi-Fi via HTTP REST API to a Python backend. The backend persists the time-series telemetry in a database, runs an automated agronomic threshold evaluation engine, and serves a live, responsive web dashboard for farmers.

When hazardous conditions occur (such as extreme heat stress, frost hazards, excessive air humidity, or heavy rainfall), automated agricultural alerts and actionable farmer advisories are generated in real-time.

```
       +--------------------+
       |  DHT11 Sensor      |
       |  (Temp & Humidity) |---+
       +--------------------+   |      +---------------+       Wi-Fi / HTTP POST       +---------------------+
                                +----->|  ESP32 Micro- |=============================> | Python Backend      |
       +--------------------+   |      |  controller   |      JSON Telemetry           | (Flask REST API)    |
       |  Rain Sensor Board |---+      +---------------+                               +----------+----------+
       |  (FC-37 + LM393)   |                                                                     |
       +--------------------+                                                                     |
                                                                                                  v
       +------------------------------------+          REST API / Dynamic Polling        +-------------------+
       | Simple Farmer Web Dashboard        | <========================================= | Database          |
       | - 4 Clean Weather Cards            |                                            | (MySQL in Docker) |
       | - Temperature & Humidity Charts    |                                            +-------------------+
       | - Recent 5 Sensor Readings Table   |
       +------------------------------------+
```

---

## 2. Key Features

- **Real-Time Telemetry Ingestion**: High-throughput REST API endpoint (`POST /api/sensor-data`) with JSON validation and physical boundary filtering.
- **Heartbeat & Connectivity Monitoring**: Automatic detection of ESP32 node connection status with visual live/offline indicators.
- **Automated Weather Alerts**:
  - **Crop Heat Stress Warning**: Triggered when temperature exceeds safe limits (> 35°C).
  - **Frost & Chilling Injury Hazard**: Triggered when temperature drops (< 10°C).
  - **Fungal Pathogen Risk Warning**: Triggered when relative humidity exceeds 85%.
  - **Heavy Precipitation & Waterlogging Warning**: Triggered when rainfall intensity exceeds 60%.
- **Configurable Agricultural Thresholds**: Farmers or administrators can adjust safety thresholds directly from the dashboard modal without touching source code.
- **Historical Analytics & Visual Trends**: Dual-axis line charts and rainfall histograms powered by **Chart.js** with date filtering and single-click CSV export.
- **Project Evaluation & Viva Simulation Toolbar**: Built-in simulator allows generating realistic scenarios (Normal, Heatwave, Frost, Heavy Rain, High Humidity) directly from the dashboard to demonstrate the system even when physical hardware is not powered on.
- **Containerized Deployment**: One-command deployment using **Docker** and **Docker Compose** with persistent database volumes.

---

## 3. Technology Stack

| Layer | Technologies Used |
| :--- | :--- |
| **Microcontroller & IoT Hardware** | ESP32 DevKit V1 (Wi-Fi 802.11 b/g/n, 2.4 GHz), Arduino C++ |
| **Sensors** | DHT11 (Digital Temperature & Humidity), FC-37 Rain Board with LM393 Comparator |
| **Backend & REST API** | Python 3.12, Flask, Flask-CORS, PyMySQL, Gunicorn |
| **Frontend UI** | HTML5, CSS3, JavaScript (ES6+), Bootstrap 5, Bootstrap Icons, Chart.js 4 |
| **Database** | MySQL 8.0 (with automated fallback to local SQLite for zero-setup execution) |
| **Containerization** | Docker, Docker Compose |

---

## 4. Project Directory Structure

```text
smart-weather-alert/
├── backend/
│   ├── app.py                     # Flask REST API, alert rules & routes
│   ├── database.py                # Database connection manager (MySQL & SQLite fallback)
│   ├── requirements.txt           # Python backend dependencies
│   └── test_system.py             # 12-point automated test suite
├── frontend/
│   ├── templates/
│   │   └── index.html             # Responsive agricultural dashboard
│   └── static/
│       ├── css/
│       │   └── style.css          # Agricultural green theme & card animations
│       └── js/
│           ├── dashboard.js       # Live polling, alert management, and threshold UI
│           └── charts.js          # Dynamic Chart.js visualizations
├── esp32/
│   ├── esp32_weather_station.ino  # Production Arduino C++ firmware
│   └── WIRING_GUIDE.md            # Hardware pinouts, schematic, and setup instructions
├── database/
│   └── schema.sql                 # MySQL schema, table definitions, and initial seeds
├── docker/
│   └── Dockerfile                 # Multi-stage production container build
├── docker-compose.yml             # Orchestration for backend and MySQL containers
├── .env.example                   # Environment variable template
├── .env                           # Active configuration file
└── README.md                      # Comprehensive academic documentation
```

---

## 5. Hardware Wiring & Pin Connections

| Sensor | Sensor Pin | ESP32 GPIO | Electrical Notes |
| :--- | :--- | :--- | :--- |
| **DHT11** | VCC | 3.3V | Connect to 3.3V power rail |
| **DHT11** | DATA | **GPIO 4** | 10kΩ pull-up resistor to 3.3V |
| **DHT11** | GND | GND | Ground rail |
| **Rain Sensor (LM393)** | VCC | 3.3V | Operating voltage: 3.3V - 5V |
| **Rain Sensor (LM393)** | GND | GND | Ground rail |
| **Rain Sensor (LM393)** | A0 (Analog) | **GPIO 34** | Must use ADC1 channel (GPIO 34) when Wi-Fi is active! |
| **Rain Sensor (LM393)** | D0 (Digital) | **GPIO 18** | Digital threshold interrupt (Active LOW) |

> **Note on ADC1 vs ADC2:** ESP32 hardware disables ADC2 when the Wi-Fi radio is broadcasting. Always connect analog sensors to ADC1 pins (GPIO 32 to 39).

---

## 6. How to Run the Application

You can run the project using **Docker Compose** (recommended for production/presentation) or **Standalone Python** (for local development).

### Method A: Running with Docker Compose (Recommended)

1. Ensure Docker Desktop is installed and running.
2. In the project root directory, run:
   ```bash
   docker-compose up --build
   ```
3. Docker will automatically:
   - Start the MySQL 8.0 container.
   - Run `database/schema.sql` to initialize tables and default thresholds.
   - Build and start the Python Flask backend container with Gunicorn.
4. Open your browser and navigate to:
   ```text
   http://localhost:5000
   ```

To stop the containers:
```bash
docker-compose down
```

---

### Method B: Running Standalone Locally (Without Docker)

1. Open a terminal in the project directory.
2. Install Python dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```
3. Start the backend:
   ```bash
   python backend/app.py
   ```
4. Open your browser and visit:
   ```text
   http://localhost:5000
   ```
*(Note: If MySQL is not running locally, the application automatically activates SQLite mode (`weather_data.db`) so all features function seamlessly).*

---

## 7. Connecting ESP32 to the Backend

1. Connect your computer and ESP32 to the **same Wi-Fi network** (or mobile hotspot).
2. Open PowerShell or Command Prompt on your computer and run:
   ```cmd
   ipconfig
   ```
   Look for the **IPv4 Address** under your active Wi-Fi adapter (e.g. `192.168.1.15`).
3. Open `esp32/esp32_weather_station.ino` in Arduino IDE.
4. Update lines 43-48 with your network details:
   ```cpp
   const char* WIFI_SSID         = "Your_WiFi_Name";
   const char* WIFI_PASSWORD     = "Your_WiFi_Password";
   const char* BACKEND_SERVER_IP = "192.168.1.15"; // Your PC's IPv4 address
   ```
5. Select Board: **DOIT ESP32 DEVKIT V1**, select your COM port, and click **Upload**.
6. Open **Serial Monitor** at **115200 baud**. You will see:
   ```text
   [WiFi] Successfully connected! Assigned IP: 192.168.1.25
   [Telemetry] Temp: 27.5 °C | Humidity: 62.0 % | Rain Intensity: 0 %
   [HTTP] Sending POST request to: http://192.168.1.15:5000/api/sensor-data
   [HTTP] Server Response Code: 201
   ```
7. Check the dashboard at `http://localhost:5000` — the values will update live without refreshing the page!

---

## 8. REST API Reference

### 1. Ingest Sensor Telemetry
- **Endpoint:** `POST /api/sensor-data`
- **Headers:** `Content-Type: application/json`, `X-API-KEY: WEATHER_FARM_KEY_2026`
- **Request Body:**
  ```json
  {
    "device_id": "ESP32_FARM_01",
    "temperature": 28.5,
    "humidity": 65.0,
    "rain_value": 45,
    "rain_detected": true
  }
  ```
- **Response (201 Created):**
  ```json
  {
    "status": "success",
    "message": "Sensor reading recorded successfully",
    "reading_id": 1,
    "alerts_triggered": []
  }
  ```

### 2. Fetch Latest Telemetry & Advisory
- **Endpoint:** `GET /api/sensor-data/latest`
- **Response (200 OK):**
  ```json
  {
    "status": "success",
    "reading": {
      "temperature": 28.5,
      "humidity": 65.0,
      "rain_value": 45,
      "rain_level": "Moderate Rain",
      "recorded_at": "2026-11-01 08:35:00"
    },
    "device": {
      "device_id": "ESP32_FARM_01",
      "is_online": true,
      "seconds_since_last_seen": 4
    },
    "agricultural_advisory": "Rainfall in progress. Pause scheduled irrigation systems."
  }
  ```

### 3. Fetch Historical Data
- **Endpoint:** `GET /api/sensor-data/history?limit=50&start_date=2026-11-01&end_date=2026-11-02`

### 4. Fetch Active Weather Alerts
- **Endpoint:** `GET /api/alerts?status=active`

### 5. Resolve Weather Alert
- **Endpoint:** `POST /api/alerts/<id>/resolve` or `POST /api/alerts/resolve-all`

### 6. Update Alert Thresholds
- **Endpoint:** `POST /api/thresholds`
- **Request Body:**
  ```json
  {
    "temperature": { "min": 10.0, "max": 35.0 },
    "humidity": { "min": 30.0, "max": 85.0 },
    "rain": { "max": 60.0 }
  }
  ```

### 7. Export Telemetry to CSV
- **Endpoint:** `GET /api/export/csv` (Downloads `.csv` file)

---

## 9. Automated Testing

The project includes an automated 12-point unit and integration test suite:

```bash
python backend/test_system.py
```

Test coverage includes:
- Health check & database connection
- Frontend template rendering
- Normal telemetry ingestion
- Automatic trigger of `HEAT_STRESS` alert
- Automatic trigger of `HEAVY_RAIN` & `HIGH_HUMIDITY` alerts
- Live dashboard status polling
- Historical data retrieval & limits
- Alert resolution logic
- Threshold configuration update
- ESP32 device heartbeat calculation
- CSV export integrity
- Weather scenario simulation engine

---

## 10. Frequently Asked MCA Viva Voce Questions & Answers

### Q1: Why did you choose the ESP32 over the traditional Arduino Uno?
**Answer:** The Arduino Uno lacks native wireless networking and requires external shields (like ESP8266 or Ethernet shields). The ESP32 is a dual-core 32-bit SoC operating at 240 MHz with built-in Wi-Fi and Bluetooth, ample flash memory (4MB), and hardware cryptographic accelerators, making it an industrial-grade, cost-effective standalone IoT node.

### Q2: How does the web dashboard update automatically without page refresh?
**Answer:** The frontend implements asynchronous polling via JavaScript `fetch()` APIs executing every 4 seconds. When new sensor packets arrive from the ESP32, the DOM elements (cards, badges, and Chart.js datasets) update smoothly without redrawing the entire HTML page.

### Q3: Why is GPIO 34 specifically used for the rain sensor analog output?
**Answer:** The ESP32 has two ADC units: ADC1 and ADC2. When the Wi-Fi radio is active, the ESP32 Wi-Fi driver internally takes control of ADC2. Consequently, reading analog pins on ADC2 (e.g. GPIO 2, 4, 12-15, 25-27) fails or returns inaccurate data. GPIO 34 belongs to ADC1, which works concurrently with Wi-Fi.

### Q4: How is alert duplicate spamming prevented when the ESP32 posts data every 5 seconds?
**Answer:** The backend alert evaluation engine implements a deduplication cooldown. Before inserting a new alert into `weather_alerts`, it queries the database to check if an active, unresolved alert of the same type (`HEAT_STRESS`, `HEAVY_RAIN`, etc.) was already registered within the last 10 minutes.

### Q5: What is the purpose of Docker and Docker Compose in this project?
**Answer:** Docker encapsulates the Python backend, dependencies, and MySQL database into isolated, reproducible containers. This eliminates the "works on my machine" problem, guarantees environment consistency, and allows spinning up the complete distributed architecture with persistent database volumes via a single command (`docker-compose up --build`).
