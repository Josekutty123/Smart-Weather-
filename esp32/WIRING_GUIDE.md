# ESP32 Hardware Wiring & Configuration Guide

**Project:** Smart Weather Alert System for Farmers Using ESP32 and IoT  
**Target:** MCA Academic Project  

---

## 1. Hardware Bill of Materials (BOM)

| Component | Description | Quantity |
| :--- | :--- | :--- |
| **ESP32 Dev Module** | ESP-WROOM-32 (30-pin or 38-pin node) with onboard Wi-Fi & Bluetooth | 1 |
| **DHT11 Sensor** | 3-pin or 4-pin Temperature & Relative Humidity Sensor module | 1 |
| **Rain Sensor Board** | FC-37 / YL-83 raindrop detection board with LM393 comparator module | 1 |
| **Breadboard** | Standard 400 or 830 tie-point solderless breadboard | 1 |
| **Jumper Wires** | Male-to-Female and Male-to-Male jumper cables | ~10 |
| **Micro-USB Cable** | High-quality data cable for power and flashing code | 1 |
| **10kΩ Resistor** | Required if using bare 4-pin DHT11 (module versions have it built-in) | 1 |

---

## 2. Complete Pin Connection Table

### A. DHT11 Temperature & Humidity Sensor
*If using a 3-pin DHT11 module (marked `+`, `-`, `out` or `S`):*
- **VCC (`+`)** $\rightarrow$ **ESP32 3.3V** (or 5V / VIN pin)
- **GND (`-`)** $\rightarrow$ **ESP32 GND**
- **DATA (`out` / `S`)** $\rightarrow$ **ESP32 GPIO 4**

*If using a bare 4-pin DHT11 sensor:*
- **Pin 1 (VCC)** $\rightarrow$ **ESP32 3.3V**
- **Pin 2 (Data)** $\rightarrow$ **ESP32 GPIO 4** (Connect 10kΩ resistor between Pin 1 & Pin 2)
- **Pin 3 (NC)** $\rightarrow$ Not connected
- **Pin 4 (GND)** $\rightarrow$ **ESP32 GND**

---

### B. Rain Sensor Module (FC-37 Rain Board + LM393 Comparator)
The rain collection board connects to the 2-pin header on the LM393 comparator module using 2 male-to-female jumper wires (polarity does not matter between board and comparator).

*From the LM393 4-pin output header to ESP32:*
- **VCC** $\rightarrow$ **ESP32 3.3V** (or VIN)
- **GND** $\rightarrow$ **ESP32 GND**
- **A0 (Analog Output)** $\rightarrow$ **ESP32 GPIO 34 (ADC1_CH6)**
- **D0 (Digital Output)** $\rightarrow$ **ESP32 GPIO 18**

> [!IMPORTANT]
> **Why GPIO 34 for Analog Input? (Key MCA Viva Question)**  
> The ESP32 has two Analog-to-Digital Converters: **ADC1** and **ADC2**. When the ESP32 Wi-Fi module is turned ON, **ADC2 is internally utilized by the Wi-Fi driver**, causing ADC2 pins (GPIO 0, 2, 4, 12, 13, 14, 15, 25, 26, 27) to return false or erratic analog values.  
> **GPIO 34 belongs to ADC1**, which remains 100% operational alongside active Wi-Fi transmission.

---

## 3. Circuit Wiring Schematic Diagram

```text
 +---------------------------------------------------------+
 |                      ESP32 NODE                         |
 |                                                         |
 |  [ 3.3V ] ---------+------------------+                 |
 |                    |                  |                 |
 |  [ GND  ] -----+---|--------------+---|-------------+   |
 |                |   |              |   |             |   |
 |  [ GPIO 4 ] ---|---|--[DATA]      |   |             |   |
 |                |   |   DHT11      |   |             |   |
 |                |   +---[VCC]      |   |             |   |
 |                +-------[GND]      |   |             |   |
 |                                   |   |             |   |
 |  [ GPIO 34 ] -----------------[A0]|   |             |   |
 |  [ GPIO 18 ] -----------------[D0]|   |             |   |
 |                                   +---[VCC]         |   |
 |                                   LM393 Rain Board  |   |
 |                                       [GND]---------+   |
 |                                         |               |
 |                                      [2-Pin]            |
 |                                         |               |
 |                                 [=== Rain Plate ===]    |
 +---------------------------------------------------------+
```

---

## 4. Arduino IDE Setup Instructions

### Step 1: Install ESP32 Board Core
1. Open **Arduino IDE**.
2. Go to **File** $\rightarrow$ **Preferences**.
3. In *Additional Boards Manager URLs*, add:
   ```text
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
4. Go to **Tools** $\rightarrow$ **Board** $\rightarrow$ **Boards Manager...**, search for `esp32` by Espressif Systems, and click **Install**.

### Step 2: Install Sensor Libraries
1. In Arduino IDE, go to **Tools** $\rightarrow$ **Manage Libraries...**
2. Search for `DHT sensor library` by **Adafruit**, click **Install** (select *Install All Dependencies* including Adafruit Unified Sensor).

### Step 3: Configure Network & Backend Settings
Open `esp32/esp32_weather_station.ino`:
```cpp
const char* WIFI_SSID     = "YOUR_WIFI_NAME";       // Your Wi-Fi name
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";   // Your Wi-Fi password
const char* BACKEND_SERVER_IP = "192.168.1.15";     // Your Laptop's LAN IP
```

#### How to find your Laptop's LAN IP:
1. Open PowerShell or Command Prompt on your computer.
2. Run:
   ```cmd
   ipconfig
   ```
3. Locate **Wireless LAN adapter Wi-Fi** and copy the **IPv4 Address** (e.g. `192.168.1.15` or `192.168.43.100`).

### Step 4: Flash the Code
1. Connect ESP32 to your laptop using the Micro-USB cable.
2. Under **Tools** $\rightarrow$ **Board**, choose **DOIT ESP32 DEVKIT V1** (or ESP32 Dev Module).
3. Under **Tools** $\rightarrow$ **Port**, choose the detected COM port (e.g., `COM3`, `COM4`).
4. Click **Upload** (Arrow icon).
   *(Note: If you see `Connecting........____`, press and hold the **BOOT** button on the ESP32 until the upload progress starts).*
5. Open **Tools** $\rightarrow$ **Serial Monitor** and set baud rate to **115200**.

You will see:
```text
[WiFi] Connecting to SSID: ...
[WiFi] Successfully connected! Assigned IP: 192.168.1.25
[Telemetry] Temp: 28.4 °C | Humidity: 65.0 %
[HTTP] Sending POST request to: http://192.168.1.15:5000/api/sensor-data
[HTTP] Server Response Code: 201
```

---

## 5. Rain Sensor Calibration
The LM393 module has a small blue potentiometer:
1. Power on the sensor.
2. When the rain sensing plate is completely dry, turn the potentiometer until the digital LED (`D0 LED`) just turns OFF.
3. Place a single drop of water on the rain plate; the LED should immediately turn ON.
4. When water is wiped off, the LED turns OFF.
