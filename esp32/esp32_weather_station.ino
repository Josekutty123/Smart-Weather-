/*
 * =====================================================================================
 * Smart Weather Alert System for Farmers Using ESP32 and IoT
 * MCA Academic Project - Arduino IDE Firmware
 * =====================================================================================
 * 
 * Target Board: ESP32 Dev Module / ESP32 WROOM-32
 * Sensors:
 *   1. DHT11: Temperature and Humidity Sensor (Connected to GPIO 4)
 *   2. Rain Sensor Module FC-37 / YL-83 with LM393 Comparator Board:
 *      - Analog Output (AO) -> GPIO 34 (ADC1 channel, safe with active Wi-Fi)
 *      - Digital Output (DO) -> GPIO 18
 * 
 * Required Libraries (Install via Arduino Library Manager):
 *   - "DHT sensor library" by Adafruit (v1.4.x)
 *   - "Adafruit Unified Sensor" by Adafruit
 *   - Built-in ESP32 libraries: WiFi.h, HTTPClient.h
 * 
 * IMPORTANT NETWORK SETUP FOR STUDENTS / EVALUATORS:
 * 1. Both your ESP32 and your computer/server running the Python backend MUST be 
 *    connected to the SAME local Wi-Fi network (or mobile hotspot).
 * 2. Find your laptop's local IPv4 address:
 *    - On Windows: Open Command Prompt, run `ipconfig`, look for "IPv4 Address"
 *      (e.g., 192.168.1.15 or 192.168.43.100).
 * 3. Update 'BACKEND_SERVER_IP' below with that IP address.
 * 4. Connecting the USB cable to your laptop powers the ESP32 and gives you Serial 
 *    output, but sensor data travels over Wi-Fi network packets to the backend!
 * =====================================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>

// -------------------------------------------------------------
// 1. Wi-Fi Configuration (Replace with your Wi-Fi or Hotspot)
// -------------------------------------------------------------
const char* WIFI_SSID     = "YOUR_WIFI_SSID";         // e.g., "Home_WiFi" or "Phone_Hotspot"
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";     // e.g., "12345678"

// -------------------------------------------------------------
// 2. Backend Server Configuration
// -------------------------------------------------------------
// DO NOT use "localhost" or "127.0.0.1" here because "localhost" from the ESP32's
// perspective would mean the ESP32 itself! Use your PC's LAN IP address.
// Automatically detected active Wi-Fi IP of your laptop: 192.168.43.250
const char* BACKEND_SERVER_IP = "192.168.43.250";     // Automatically detected LAN IP
const int   BACKEND_PORT      = 5000;
const char* API_ENDPOINT      = "/api/sensor-data";
const char* API_KEY           = "WEATHER_FARM_KEY_2026";
const char* DEVICE_ID         = "ESP32_FARM_01";

// -------------------------------------------------------------
// 3. Hardware Pin Definitions
// -------------------------------------------------------------
#define DHTPIN        4       // GPIO 4 connected to DHT11 Data pin
#define DHTTYPE       DHT11   // DHT 11 sensor model

#define RAIN_ANALOG_PIN   34  // GPIO 34 (ADC1_CH6) connected to Rain Module AO
#define RAIN_DIGITAL_PIN  18  // GPIO 18 connected to Rain Module DO

#define STATUS_LED_PIN    2   // Onboard Blue LED on ESP32 (GPIO 2)

// Transmission Interval (Milliseconds)
const unsigned long SEND_INTERVAL_MS = 6000; // Send telemetry every 6 seconds
unsigned long lastSendTime = 0;

// Initialize DHT Sensor
DHT dht(DHTPIN, DHTTYPE);

// -------------------------------------------------------------
// Helper: Connect and Maintain Wi-Fi Connection
// -------------------------------------------------------------
void connectToWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.println();
  Serial.print("[WiFi] Connecting to SSID: ");
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 25) {
    delay(500);
    Serial.print(".");
    digitalWrite(STATUS_LED_PIN, !digitalRead(STATUS_LED_PIN)); // Blink LED while connecting
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(STATUS_LED_PIN, HIGH); // Solid ON when connected
    Serial.println();
    Serial.println("[WiFi] Successfully connected!");
    Serial.print("[WiFi] ESP32 Assigned IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("[WiFi] Signal Strength (RSSI): ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    digitalWrite(STATUS_LED_PIN, LOW);
    Serial.println();
    Serial.println("[WiFi] Connection failed. Will retry in next loop cycle.");
  }
}

// -------------------------------------------------------------
// Arduino Setup Function
// -------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n=======================================================");
  Serial.println(" Smart Weather Alert System for Farmers - ESP32 Node");
  Serial.println(" MCA Academic Project • IoT & Cloud Telemetry");
  Serial.println("=======================================================");

  pinMode(STATUS_LED_PIN, OUTPUT);
  pinMode(RAIN_ANALOG_PIN, INPUT);
  pinMode(RAIN_DIGITAL_PIN, INPUT_PULLUP);

  // Initialize DHT11 sensor
  dht.begin();
  Serial.println("[Sensors] DHT11 initialized on GPIO 4");
  Serial.println("[Sensors] Rain sensor initialized on GPIO 34 (Analog) & GPIO 18 (Digital)");

  // Connect to Local Wi-Fi
  connectToWiFi();
}

// -------------------------------------------------------------
// Main Arduino Loop Function
// -------------------------------------------------------------
void loop() {
  // Reconnect Wi-Fi if connection was lost
  if (WiFi.status() != WL_CONNECTED) {
    connectToWiFi();
  }

  // Periodic sensor sampling and transmission
  unsigned long currentMillis = millis();
  if (currentMillis - lastSendTime >= SEND_INTERVAL_MS) {
    lastSendTime = currentMillis;

    // 1. Read DHT11 Temperature and Humidity
    float humidity = dht.readHumidity();
    float temperature = dht.readTemperature(); // Celsius

    // Check for sensor read failure
    if (isnan(humidity) || isnan(temperature)) {
      Serial.println("[ERROR] Failed to read from DHT11 sensor! Check wiring.");
      return;
    }

    // 2. Read Rain Sensor
    // Raw ADC reading on ESP32 is 12-bit (0 - 4095).
    // Dry sensor: ~3500 - 4095
    // Saturated/heavy rain: ~0 - 1000
    int rawRainValue = analogRead(RAIN_ANALOG_PIN);
    int rainDigital = digitalRead(RAIN_DIGITAL_PIN); // LM393 DO is Active LOW (0 = rain, 1 = dry)

    // Calculate Rain Intensity Percentage (0% = Bone dry, 100% = Maximum deluge)
    int rainIntensityPercent = map(rawRainValue, 4095, 0, 0, 100);
    if (rainIntensityPercent < 0) rainIntensityPercent = 0;
    if (rainIntensityPercent > 100) rainIntensityPercent = 100;

    bool isRaining = (rainDigital == LOW) || (rainIntensityPercent > 15);

    // Print values to Serial Monitor for student debugging
    Serial.println("\n-------------------------------------------------------");
    Serial.printf("[Telemetry] Temp: %.1f °C | Humidity: %.1f %%\n", temperature, humidity);
    Serial.printf("[Telemetry] Rain Raw ADC: %d | Rain Intensity: %d %% | Status: %s\n",
                  rawRainValue, rainIntensityPercent, isRaining ? "RAIN DETECTED" : "NO RAIN");

    // 3. Transmit telemetry via HTTP POST to Python Backend
    if (WiFi.status() == WL_CONNECTED) {
      transmitSensorData(temperature, humidity, rainIntensityPercent, isRaining);
    } else {
      Serial.println("[WiFi] Cannot transmit data: Not connected to Wi-Fi");
    }
  }
}

// -------------------------------------------------------------
// Function to Send JSON Payload to Backend REST API
// -------------------------------------------------------------
void transmitSensorData(float temp, float hum, int rainIntensity, bool isRaining) {
  HTTPClient http;

  // Build full server URL
  String serverUrl = String("http://") + BACKEND_SERVER_IP + ":" + String(BACKEND_PORT) + API_ENDPOINT;
  Serial.print("[HTTP] Sending POST request to: ");
  Serial.println(serverUrl);

  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-KEY", API_KEY);
  http.setTimeout(4000); // 4-second network timeout

  // Construct JSON body
  char jsonBuffer[256];
  snprintf(jsonBuffer, sizeof(jsonBuffer),
           "{\"device_id\":\"%s\",\"temperature\":%.2f,\"humidity\":%.2f,\"rain_value\":%d,\"rain_detected\":%s,\"api_key\":\"%s\"}",
           DEVICE_ID,
           temp,
           hum,
           rainIntensity,
           isRaining ? "true" : "false",
           API_KEY);

  Serial.print("[HTTP] Payload: ");
  Serial.println(jsonBuffer);

  // Send POST request
  int httpResponseCode = http.POST(jsonBuffer);

  if (httpResponseCode > 0) {
    String response = http.getString();
    Serial.printf("[HTTP] Server Response Code: %d\n", httpResponseCode);
    Serial.print("[HTTP] Response Body: ");
    Serial.println(response);

    // Blink onboard LED to indicate successful transmission
    digitalWrite(STATUS_LED_PIN, LOW);
    delay(100);
    digitalWrite(STATUS_LED_PIN, HIGH);
  } else {
    Serial.printf("[HTTP] POST failed. Error: %s\n", http.errorToString(httpResponseCode).c_str());
    Serial.println("[HINT] Ensure backend server is running and laptop firewall is not blocking port 5000.");
  }

  http.end(); // Free network resources
}
