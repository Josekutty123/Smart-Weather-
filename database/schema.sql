-- Smart Weather Alert System for Farmers
-- MySQL Database Schema & Initial Seed Data

CREATE DATABASE IF NOT EXISTS weather_db;
USE weather_db;

-- 1. Devices Table: Keeps track of registered ESP32 units
CREATE TABLE IF NOT EXISTS devices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(50) NOT NULL UNIQUE,
    device_name VARCHAR(100) DEFAULT 'ESP32 Farm Node 1',
    ip_address VARCHAR(45) NULL,
    mac_address VARCHAR(30) NULL,
    firmware_version VARCHAR(20) DEFAULT '1.0.0',
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    status ENUM('ONLINE', 'OFFLINE') DEFAULT 'ONLINE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. Sensor Readings Table: High-resolution telemetry data from ESP32
CREATE TABLE IF NOT EXISTS sensor_readings (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(50) NOT NULL,
    temperature DECIMAL(5, 2) NOT NULL COMMENT 'Temperature in Celsius',
    humidity DECIMAL(5, 2) NOT NULL COMMENT 'Relative Humidity in percentage',
    rain_value INT NOT NULL COMMENT 'Raw ADC / Normalized rain value (0-100 or 0-4095)',
    rain_detected TINYINT(1) NOT NULL DEFAULT 0 COMMENT '1 if rain is actively detected, 0 otherwise',
    rain_level VARCHAR(30) DEFAULT 'No Rain' COMMENT 'No Rain, Light Rain, Moderate Rain, Heavy Rain',
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_recorded_at (recorded_at),
    INDEX idx_device_id (device_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. Alert Thresholds Table: Farmer/Admin configurable safety bounds
CREATE TABLE IF NOT EXISTS alert_thresholds (
    id INT AUTO_INCREMENT PRIMARY KEY,
    parameter_key VARCHAR(50) NOT NULL UNIQUE,
    parameter_name VARCHAR(100) NOT NULL,
    unit VARCHAR(15) NOT NULL,
    min_value DECIMAL(6, 2) NULL,
    max_value DECIMAL(6, 2) NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. Weather Alerts Table: Automated agricultural warnings
CREATE TABLE IF NOT EXISTS weather_alerts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL COMMENT 'HEAT_STRESS, FROST_RISK, HEAVY_RAIN, HIGH_HUMIDITY, SENSOR_OFFLINE',
    severity ENUM('INFO', 'WARNING', 'DANGER') DEFAULT 'WARNING',
    message TEXT NOT NULL,
    agricultural_advice TEXT NOT NULL COMMENT 'Actionable guidance for farmers',
    sensor_value DECIMAL(6, 2) NULL,
    threshold_value DECIMAL(6, 2) NULL,
    is_resolved TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL,
    INDEX idx_created_at (created_at),
    INDEX idx_is_resolved (is_resolved)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Seed Initial Device
INSERT INTO devices (device_id, device_name, ip_address, status)
VALUES ('ESP32_FARM_01', 'Greenhouse & Field Node', '192.168.1.100', 'ONLINE')
ON DUPLICATE KEY UPDATE device_name=VALUES(device_name);

-- Seed Default Agricultural Thresholds
INSERT INTO alert_thresholds (parameter_key, parameter_name, unit, min_value, max_value, description)
VALUES 
    ('temperature', 'Field Temperature', '°C', 10.00, 35.00, 'Alert if temperature drops below 10°C (frost hazard) or rises above 35°C (crop heat stress).'),
    ('humidity', 'Relative Humidity', '%', 30.00, 85.00, 'Alert if humidity exceeds 85% (fungal pest infestation hazard) or drops below 30% (excessive transpiration).'),
    ('rain', 'Rainfall Threshold', '%', NULL, 60.00, 'Alert when rainfall intensity exceeds 60% (heavy downpour, waterlogging danger).')
ON DUPLICATE KEY UPDATE 
    parameter_name=VALUES(parameter_name),
    min_value=VALUES(min_value),
    max_value=VALUES(max_value),
    description=VALUES(description);

-- Seed Initial Sample Alert
INSERT INTO weather_alerts (alert_type, severity, message, agricultural_advice, sensor_value, threshold_value, is_resolved)
VALUES (
    'SYSTEM_INIT', 
    'INFO', 
    'Smart Weather Alert System initialized successfully.', 
    'Sensors are online. Ensure ESP32 is powered and connected to Wi-Fi.', 
    0, 
    0, 
    0
);
