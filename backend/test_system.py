"""
Automated Test Suite for Smart Weather Alert System
Tests every API endpoint, alert trigger, database persistence, and CSV export.
"""

import unittest
import json
import os
import sys

# Ensure backend directory is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
import database


class WeatherSystemTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_01_health_check(self):
        """Test the system health check endpoint."""
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "healthy")
        print("[PASS] Health Check Passed:", data["database_mode"])

    def test_02_dashboard_html(self):
        """Test that the frontend dashboard loads successfully."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Smart Weather Monitoring System", res.data)
        self.assertIn(b"Temperature", res.data)
        print("[PASS] Frontend Dashboard Template Rendered Successfully")

    def test_03_post_normal_sensor_data(self):
        """Test ESP32 telemetry ingestion under normal conditions."""
        payload = {
            "device_id": "ESP32_FARM_01",
            "temperature": 26.5,
            "humidity": 60.0,
            "rain_value": 0,
            "rain_detected": False,
            "api_key": "WEATHER_FARM_KEY_2026"
        }
        res = self.client.post(
            "/api/sensor-data",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertIn("reading_id", data)
        print(f"[PASS] Normal Sensor Ingestion Passed: Reading ID #{data['reading_id']}")

    def test_04_post_heatwave_and_trigger_alert(self):
        """Test high temperature triggering HEAT_STRESS alert."""
        payload = {
            "device_id": "ESP32_FARM_01",
            "temperature": 38.5,  # Exceeds 35°C limit
            "humidity": 45.0,
            "rain_value": 0,
            "rain_detected": False,
            "api_key": "WEATHER_FARM_KEY_2026"
        }
        res = self.client.post(
            "/api/sensor-data",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(len(data["alerts_triggered"]) >= 1)
        self.assertEqual(data["alerts_triggered"][0]["alert_type"], "HEAT_STRESS")
        print("[PASS] Heatwave Alert Triggered Correctly:", data["alerts_triggered"][0]["message"])

    def test_05_post_heavy_rain_and_trigger_alert(self):
        """Test heavy rain triggering alert."""
        payload = {
            "device_id": "ESP32_FARM_01",
            "temperature": 22.0,
            "humidity": 92.0,     # Also triggers HIGH_HUMIDITY
            "rain_value": 0,      # Active-LOW digital pin 27: 0 = water detected
            "rain_detected": True,
            "rain_status": "Rain Detected",
            "api_key": "WEATHER_FARM_KEY_2026"
        }
        res = self.client.post(
            "/api/sensor-data",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        triggered_types = [a["alert_type"] for a in data["alerts_triggered"]]
        self.assertTrue("RAIN_DETECTED" in triggered_types or "HEAVY_RAIN" in triggered_types)
        print("[PASS] Rain & High Humidity Alerts Triggered Correctly:", triggered_types)

    def test_06_get_latest_sensor_data(self):
        """Test retrieving latest sensor readings and advisory."""
        res = self.client.get("/api/sensor-data/latest")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertIsNotNone(data["reading"])
        self.assertTrue(data["device"]["is_online"])
        self.assertIn("agricultural_advisory", data)
        print(f"[PASS] Latest Telemetry: Temp={data['reading']['temperature']}C | Online={data['device']['is_online']}")

    def test_07_get_sensor_history(self):
        """Test historical readings API."""
        res = self.client.get("/api/sensor-data/history?limit=10")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertGreaterEqual(len(data["readings"]), 3)
        print(f"[PASS] Historical Data Retrieved: {len(data['readings'])} records")

    def test_08_get_and_resolve_alerts(self):
        """Test alert listing and resolution."""
        # List active alerts
        res = self.client.get("/api/alerts?status=active")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        alerts = data["alerts"]
        self.assertGreaterEqual(len(alerts), 1)
        target_id = alerts[0]["id"]

        # Resolve single alert
        res_res = self.client.post(f"/api/alerts/{target_id}/resolve")
        self.assertEqual(res_res.status_code, 200)
        
        # Resolve all alerts
        res_all = self.client.post("/api/alerts/resolve-all")
        self.assertEqual(res_all.status_code, 200)
        print("[PASS] Alert Resolution API Tested Successfully")

    def test_09_threshold_crud(self):
        """Test getting and updating alert threshold settings."""
        # Get current
        res = self.client.get("/api/thresholds")
        self.assertEqual(res.status_code, 200)
        initial = res.get_json()["thresholds"]
        self.assertTrue(len(initial) >= 3)

        # Update
        update_payload = {
            "temperature": {"min": 12.0, "max": 36.0},
            "humidity": {"min": 25.0, "max": 82.0},
            "rain": {"max": 65.0}
        }
        res_update = self.client.post(
            "/api/thresholds",
            data=json.dumps(update_payload),
            content_type="application/json"
        )
        self.assertEqual(res_update.status_code, 200)
        print("[PASS] Alert Threshold Configuration API Updated Successfully")

    def test_10_device_status_heartbeat(self):
        """Test device status and connectivity check."""
        res = self.client.get("/api/device/status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["device_id"], "ESP32_FARM_01")
        print(f"[PASS] Device Status Check: {data['device_id']} is {data['connection_state']}")

    def test_11_csv_export(self):
        """Test sensor telemetry CSV download."""
        res = self.client.get("/api/export/csv")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, "text/csv")
        self.assertIn(b"Temperature", res.data)
        self.assertIn(b"Humidity", res.data)
        print("[PASS] CSV Telemetry Export Verified")

    def test_12_simulation_scenario(self):
        """Test scenario simulation endpoint."""
        res = self.client.post(
            "/api/sensor-data/simulate",
            data=json.dumps({"scenario": "frost"}),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertLess(data["data"]["temperature"], 10.0)
        print(f"[PASS] Simulation Scenario 'frost' Tested: Temp={data['data']['temperature']}C")

    def test_13_esp32_active_low_rain_detection(self):
        """Test ESP32 active-LOW rain detection ingestion (0 = Water Detected, 1 = No Water Detected)."""
        # Test 1: Wet Sensor reading
        wet_payload = {
            "device_id": "ESP32_FARM_01",
            "temperature": 29.0,
            "humidity": 75.0,
            "rain_status": "Water Detected",
            "rain_detected": True,
            "rain_value": 0
        }
        res_wet = self.client.post(
            "/api/sensor-data",
            data=json.dumps(wet_payload),
            content_type="application/json"
        )
        self.assertEqual(res_wet.status_code, 201)
        wet_data = res_wet.get_json()
        self.assertTrue(wet_data["data"]["rain_detected"])
        self.assertEqual(wet_data["data"]["rain_status"], "Water Detected")
        self.assertEqual(wet_data["data"]["rain_value"], 0)

        # Verify latest endpoint reflects water detected
        res_latest_wet = self.client.get("/api/sensor-data/latest")
        self.assertEqual(res_latest_wet.status_code, 200)
        latest_wet = res_latest_wet.get_json()
        self.assertTrue(latest_wet["reading"]["rain_detected"])
        self.assertEqual(latest_wet["reading"]["rain_status"], "Water Detected")

        # Test 2: Dry Sensor reading
        dry_payload = {
            "device_id": "ESP32_FARM_01",
            "temperature": 29.0,
            "humidity": 75.0,
            "rain_status": "No Water Detected",
            "rain_detected": False,
            "rain_value": 1
        }
        res_dry = self.client.post(
            "/api/sensor-data",
            data=json.dumps(dry_payload),
            content_type="application/json"
        )
        self.assertEqual(res_dry.status_code, 201)
        dry_data = res_dry.get_json()
        self.assertFalse(dry_data["data"]["rain_detected"])
        self.assertEqual(dry_data["data"]["rain_status"], "No Water Detected")
        self.assertEqual(dry_data["data"]["rain_value"], 1)

        # Verify latest endpoint reflects no water detected
        res_latest_dry = self.client.get("/api/sensor-data/latest")
        self.assertEqual(res_latest_dry.status_code, 200)
        latest_dry = res_latest_dry.get_json()
        self.assertFalse(latest_dry["reading"]["rain_detected"])
        self.assertEqual(latest_dry["reading"]["rain_status"], "No Water Detected")

        print("[PASS] ESP32 Active-LOW Water Detection Ingestion & Retrieval Verified")


if __name__ == "__main__":
    unittest.main(verbosity=2)
