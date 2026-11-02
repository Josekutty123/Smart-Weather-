import os
import sqlite3
import pymysql
import logging
from pymysql.cursors import DictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger("WeatherApp.DB")

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "weather_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "weather_secret_123")
DB_NAME = os.getenv("DB_NAME", "weather_db")
ENABLE_FALLBACK = os.getenv("ENABLE_DB_FALLBACK", "true").lower() in ("true", "1", "yes")

_db_mode = None  # 'mysql' or 'sqlite'
SQLITE_PATH = os.path.join(os.path.dirname(__file__), "weather_data.db")


def determine_database():
    """Detect whether MySQL is accessible. If not, use SQLite fallback if enabled."""
    global _db_mode
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            charset="utf8mb4",
            connect_timeout=3
        )
        conn.close()
        _db_mode = "mysql"
        logger.info(f"Connected successfully to MySQL at {DB_HOST}:{DB_PORT}")
        return "mysql"
    except Exception as e:
        if ENABLE_FALLBACK:
            _db_mode = "sqlite"
            logger.warning(f"MySQL unavailable ({e}). Falling back to local SQLite: {SQLITE_PATH}")
            return "sqlite"
        else:
            _db_mode = "mysql"
            logger.error(f"Failed to connect to MySQL: {e}")
            raise e


def get_db_mode():
    global _db_mode
    if _db_mode is None:
        determine_database()
    return _db_mode


def get_connection():
    """Get active database connection based on mode."""
    mode = get_db_mode()
    if mode == "mysql":
        return pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=True
        )
    else:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def init_db():
    """Initialize database tables and initial seed configuration."""
    mode = get_db_mode()
    
    if mode == "mysql":
        # Create database if not exists
        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            charset="utf8mb4"
        )
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME};")
        conn.close()

        # Connect to database and create tables
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("""
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
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                device_id VARCHAR(50) NOT NULL,
                temperature DECIMAL(5, 2) NOT NULL,
                humidity DECIMAL(5, 2) NOT NULL,
                rain_value INT NOT NULL,
                rain_detected TINYINT(1) NOT NULL DEFAULT 0,
                rain_level VARCHAR(30) DEFAULT 'No Rain',
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_recorded_at (recorded_at),
                INDEX idx_device_id (device_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            cur.execute("""
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
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS weather_alerts (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                alert_type VARCHAR(50) NOT NULL,
                severity ENUM('INFO', 'WARNING', 'DANGER') DEFAULT 'WARNING',
                message TEXT NOT NULL,
                agricultural_advice TEXT NOT NULL,
                sensor_value DECIMAL(6, 2) NULL,
                threshold_value DECIMAL(6, 2) NULL,
                is_resolved TINYINT(1) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP NULL,
                INDEX idx_created_at (created_at),
                INDEX idx_is_resolved (is_resolved)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # Seed device
            cur.execute("""
            INSERT INTO devices (device_id, device_name, ip_address, status)
            VALUES ('ESP32_FARM_01', 'Greenhouse & Field Node', '192.168.1.100', 'ONLINE')
            ON DUPLICATE KEY UPDATE device_name=VALUES(device_name);
            """)

            # Seed default thresholds
            cur.execute("""
            INSERT INTO alert_thresholds (parameter_key, parameter_name, unit, min_value, max_value, description)
            VALUES 
                ('temperature', 'Field Temperature', '°C', 10.00, 35.00, 'Alert if temperature drops below 10°C (frost risk) or exceeds 35°C (crop heat stress).'),
                ('humidity', 'Relative Humidity', '%', 30.00, 85.00, 'Alert if humidity exceeds 85% (fungal pest hazard) or drops below 30% (moisture stress).'),
                ('rain', 'Rainfall Threshold', '%', NULL, 60.00, 'Alert when rainfall intensity exceeds 60% (heavy downpour).')
            ON DUPLICATE KEY UPDATE 
                min_value=VALUES(min_value), max_value=VALUES(max_value);
            """)
        conn.close()

    else:
        # SQLite mode
        conn = get_connection()
        cur = conn.cursor()
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL UNIQUE,
            device_name TEXT DEFAULT 'ESP32 Farm Node 1',
            ip_address TEXT,
            mac_address TEXT,
            firmware_version TEXT DEFAULT '1.0.0',
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'ONLINE',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sensor_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            temperature REAL NOT NULL,
            humidity REAL NOT NULL,
            rain_value INTEGER NOT NULL,
            rain_detected INTEGER NOT NULL DEFAULT 0,
            rain_level TEXT DEFAULT 'No Rain',
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS alert_thresholds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parameter_key TEXT NOT NULL UNIQUE,
            parameter_name TEXT NOT NULL,
            unit TEXT NOT NULL,
            min_value REAL,
            max_value REAL,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS weather_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT NOT NULL,
            severity TEXT DEFAULT 'WARNING',
            message TEXT NOT NULL,
            agricultural_advice TEXT NOT NULL,
            sensor_value REAL,
            threshold_value REAL,
            is_resolved INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP
        );

        INSERT OR IGNORE INTO devices (device_id, device_name, ip_address, status)
        VALUES ('ESP32_FARM_01', 'Greenhouse & Field Node', '192.168.1.100', 'ONLINE');

        INSERT OR IGNORE INTO alert_thresholds (parameter_key, parameter_name, unit, min_value, max_value, description)
        VALUES 
            ('temperature', 'Field Temperature', '°C', 10.00, 35.00, 'Alert if temperature drops below 10°C (frost risk) or exceeds 35°C (crop heat stress).'),
            ('humidity', 'Relative Humidity', '%', 30.00, 85.00, 'Alert if humidity exceeds 85% (fungal pest hazard) or drops below 30% (moisture stress).'),
            ('rain', 'Rainfall Threshold', '%', NULL, 60.00, 'Alert when rainfall intensity exceeds 60% (heavy downpour).');
        """)
        conn.commit()
        conn.close()


def query_all(query, params=None):
    """Execute query and return list of dictionaries."""
    mode = get_db_mode()
    conn = get_connection()
    try:
        if mode == "mysql":
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                return cur.fetchall()
        else:
            # For SQLite, convert %s to ?
            sqlite_q = query.replace("%s", "?")
            cur = conn.cursor()
            cur.execute(sqlite_q, params or ())
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    finally:
        conn.close()


def query_one(query, params=None):
    """Execute query and return a single row dictionary or None."""
    mode = get_db_mode()
    conn = get_connection()
    try:
        if mode == "mysql":
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                return cur.fetchone()
        else:
            sqlite_q = query.replace("%s", "?")
            cur = conn.cursor()
            cur.execute(sqlite_q, params or ())
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def execute_commit(query, params=None):
    """Execute insert/update/delete query and return lastrowid."""
    mode = get_db_mode()
    conn = get_connection()
    try:
        if mode == "mysql":
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                return cur.lastrowid
        else:
            sqlite_q = query.replace("%s", "?")
            cur = conn.cursor()
            cur.execute(sqlite_q, params or ())
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()
