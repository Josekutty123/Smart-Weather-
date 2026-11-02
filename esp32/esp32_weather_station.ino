/*
 * =====================================================================================
 * Smart Weather Alert System for Farmers Using ESP32 and IoT
 * MCA Academic Project - Arduino IDE Firmware
 * =====================================================================================
 * 
 * Hardware Connections:
 *   1. DHT11 Sensor:
 *      - VCC -> 3.3V (or 5V)
 *      - GND -> GND
 *      - Data -> GPIO 4
 * 
 *   2. Rain Sensor Module (FC-37 Rain Board + LM393 Comparator):
 *      - VCC -> 3.3V (or 5V)
 *      - GND -> GND
 *      - DO (Digital Output) -> GPIO 0
 * 
 * Required Libraries (Install via Arduino Library Manager):
 *   - "DHT sensor library" by Adafruit
 *   - "Adafruit Unified Sensor" by Adafruit
 *   - Built-in ESP32 libraries: WiFi.h, HTTPClient.h
 * =====================================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>

// -------------------------------------------------------------
// 1. Wi-Fi Configuration
// -------------------------------------------------------------
const char* WIFI_SSID     = "YOUR_WIFI_SSID";         // Replace with your Wi-Fi SSID
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";     // Replace with your Wi-Fi Password

// -------------------------------------------------------------
// 2. Backend Server Configuration
// -------------------------------------------------------------
// Update with your laptop's local LAN IP address
const char* BACKEND_SERVER_IP = "192.168.43.250";
const int   BACKEND_PORT      = 5000;
const char* API_ENDPOINT      = "/api/sensor-data";
const char* API_KEY           = "WEATHER_FARM_KEY_2026";
const char* DEVICE_ID         = "ESP32_FARM_01";

// -------------------------------------------------------------
// 3. Hardware Pin Definitions
// -------------------------------------------------------------
#define DHTPIN            4   // GPIO 4 connected to DHT11 Data pin
#define DHTTYPE           DHT11

#define RAIN_DIGITAL_PIN  0   // GPIO 0 connected to Rain Sensor Digital Output (DO)
#define STATUS_LED_PIN    2   // Onboard Blue LED on ESP32

// Transmission Interval: Telemetry sent every 4 seconds
const unsigned long SEND_INTERVAL_MS = 4000;
unsigned long lastSendTime = 0;

// Initialize DHT Sensor
DHT dht(DHTPIN, DHTTYPE);

// -------------------------------------------------------------
// Helper: Connect and Maintain Wi-Fi Connection
// -------------------------------------------------------------
void connectToWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 25) {
    delay(500);
    digitalWrite(STATUS_LED_PIN, !digitalRead(STATUS_LED_PIN)); // Blink LED while connecting
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(STATUS_LED_PIN, HIGH); // Solid ON when connected
  } else {
    digitalWrite(STATUS_LED_PIN, LOW);
  }
}

// -------------------------------------------------------------
// Setup Function
// -------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(STATUS_LED_PIN, OUTPUT);
  pinMode(RAIN_DIGITAL_PIN, INPUT_PULLUP); // Rain sensor digital pin

  dht.begin();
  connectToWiFi();
}

// -------------------------------------------------------------
// Main Loop Function
// -------------------------------------------------------------
void loop() {
  // Maintain Wi-Fi Connection
  if (WiFi.status() != WL_CONNECTED) {
    connectToWiFi();
  }

  unsigned long currentMillis = millis();
  if (currentMillis - lastSendTime >= SEND_INTERVAL_MS) {
    lastSendTime = currentMillis;

    // 1. Read DHT11 Temperature and Humidity
    float humidity = dht.readHumidity();
    float temperature = dht.readTemperature(); // Celsius

    if (isnan(humidity) || isnan(temperature)) {
      Serial.println("[ERROR] Failed to read from DHT11 sensor! Check wiring on GPIO 4.");
      return;
    }

    // 2. Read Digital Rain Sensor (Active-LOW: 0 = Water Detected, 1 = No Water Detected)
    int rainDigital = digitalRead(RAIN_DIGITAL_PIN);
    bool isWaterDetected = (rainDigital == LOW);
    const char* rainStatus = isWaterDetected ? "Water Detected" : "No Water Detected";

    // 3. Simplified Serial Monitor Output
    Serial.println();
    Serial.println("SMART WEATHER MONITORING");
    Serial.println();
    Serial.print("Temperature: ");
    Serial.print((int)round(temperature));
    Serial.println(" °C");
    Serial.print("Humidity: ");
    Serial.print((int)round(humidity));
    Serial.println(" %");
    Serial.print("Rain Status: ");
    Serial.println(rainStatus);

    // 4. Transmit Telemetry to Flask API via HTTP POST
    if (WiFi.status() == WL_CONNECTED) {
      transmitSensorData(temperature, humidity, isWaterDetected, rainStatus);
    }
  }
}

// -------------------------------------------------------------
// Function to Send JSON Payload to Backend REST API
// -------------------------------------------------------------
void transmitSensorData(float temp, float hum, bool isWaterDetected, const char* rainStatus) {
  HTTPClient http;

  String serverUrl = String("http://") + BACKEND_SERVER_IP + ":" + String(BACKEND_PORT) + API_ENDPOINT;

  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-KEY", API_KEY);
  http.setTimeout(4000); // 4-second network timeout

  // Construct JSON body
  char jsonBuffer[256];
  snprintf(jsonBuffer, sizeof(jsonBuffer),
           "{\"device_id\":\"%s\",\"temperature\":%.1f,\"humidity\":%.1f,\"rain_status\":\"%s\",\"rain_detected\":%s,\"rain_value\":%d,\"api_key\":\"%s\"}",
           DEVICE_ID,
           temp,
           hum,
           rainStatus,
           isWaterDetected ? "true" : "false",
           isWaterDetected ? 0 : 1,
           API_KEY);

  int httpResponseCode = http.POST(jsonBuffer);

  if (httpResponseCode > 0) {
    // Quick blink to indicate successful transmission
    digitalWrite(STATUS_LED_PIN, LOW);
    delay(80);
    digitalWrite(STATUS_LED_PIN, HIGH);
  }

  http.end(); // Free network resources
}
