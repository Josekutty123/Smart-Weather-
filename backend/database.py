import os
import sqlite3
import pymysql
import logging
from pymysql.cursors import DictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger("WeatherApp.DB")

# Environment Variables for Database Configuration
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
try:
    DB_PORT = int(os.getenv("DB_PORT", "3306") or 3306)
except ValueError:
    DB_PORT = 3306
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "smart_weather_db")
DB_SSL_CA = os.getenv("DB_SSL_CA", "").strip()
ENABLE_FALLBACK = os.getenv("ENABLE_DB_FALLBACK", "true").lower() in ("true", "1", "yes")

_db_mode = None  # 'mysql' or 'sqlite'
SQLITE_PATH = os.path.join(os.path.dirname(__file__), "weather_data.db")


def get_mysql_ssl_config():
    """
    Build SSL config dictionary for PyMySQL if CA certificate is configured.
    Supports TiDB Cloud and secure MySQL connections.
    """
    if DB_SSL_CA:
        if os.path.exists(DB_SSL_CA):
            return {"ca": DB_SSL_CA}
        else:
            logger.warning(f"Configured DB_SSL_CA path not found on filesystem: {DB_SSL_CA}")
            return {"ca": DB_SSL_CA}

    # Auto-detect standard Linux CA bundle if connecting to remote host on Render / cloud Linux
    if os.path.exists("/etc/ssl/certs/ca-certificates.crt") and DB_HOST not in ("127.0.0.1", "localhost", ""):
        return {"ca": "/etc/ssl/certs/ca-certificates.crt"}

    return None


def get_mysql_connection(cursorclass=None, autocommit=True):
    """
    Create a secure PyMySQL connection using environment configuration.
    Applies SSL certificate if configured or in cloud environment.
    """
    conn_params = {
        "host": DB_HOST,
        "port": DB_PORT,
        "user": DB_USER,
        "password": DB_PASSWORD,
        "database": DB_NAME,
        "charset": "utf8mb4",
        "connect_timeout": 10,
        "autocommit": autocommit
    }
    if cursorclass:
        conn_params["cursorclass"] = cursorclass

    ssl_config = get_mysql_ssl_config()
    if ssl_config:
        conn_params["ssl"] = ssl_config

    return pymysql.connect(**conn_params)


def determine_database():
    """
    Detect whether MySQL / TiDB Cloud is accessible.
    If connection fails and ENABLE_DB_FALLBACK is enabled, fall back to SQLite for local development.
    If ENABLE_DB_FALLBACK is false (e.g. on Render), raise the exception immediately.
    """
    global _db_mode
    try:
        conn = get_mysql_connection()
        conn.close()
        _db_mode = "mysql"
        logger.info(f"Connected successfully to MySQL/TiDB at {DB_HOST}:{DB_PORT}/{DB_NAME}")
        return "mysql"
    except Exception as e:
        if ENABLE_FALLBACK:
            _db_mode = "sqlite"
            logger.warning(f"MySQL/TiDB unavailable ({e}). Falling back to local SQLite: {SQLITE_PATH}")
            return "sqlite"
        else:
            _db_mode = "mysql"
            logger.error(f"Failed to connect to MySQL/TiDB at {DB_HOST}:{DB_PORT}/{DB_NAME} ({e}) - DB fallback is disabled.")
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
        return get_mysql_connection(cursorclass=DictCursor, autocommit=True)
    else:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def init_db():
    """
    Initialize database tables and initial seed configuration.
    Creates tables directly in the selected database (smart_weather_db / DB_NAME).
    Does NOT attempt to create or modify other databases, ensuring compatibility with TiDB Cloud.
    """
    mode = get_db_mode()

    if mode == "mysql":
        # Connect directly to target database
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
                rain_status VARCHAR(50) DEFAULT 'No Rain',
                rain_level VARCHAR(30) DEFAULT 'No Rain',
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_recorded_at (recorded_at),
                INDEX idx_device_id (device_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # Migration: Ensure rain_status column exists in MySQL table
            try:
                cur.execute("SHOW COLUMNS FROM sensor_readings LIKE 'rain_status';")
                if not cur.fetchone():
                    cur.execute("ALTER TABLE sensor_readings ADD COLUMN rain_status VARCHAR(50) DEFAULT 'No Rain' AFTER rain_detected;")
            except Exception as mig_e:
                logger.warning(f"MySQL migration rain_status notice: {mig_e}")

            # Migration: Ensure rain_level column exists in MySQL table
            try:
                cur.execute("SHOW COLUMNS FROM sensor_readings LIKE 'rain_level';")
                if not cur.fetchone():
                    cur.execute("ALTER TABLE sensor_readings ADD COLUMN rain_level VARCHAR(30) DEFAULT 'No Rain' AFTER rain_status;")
            except Exception as mig_e:
                logger.warning(f"MySQL migration rain_level notice: {mig_e}")

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
            rain_status TEXT DEFAULT 'No Rain',
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

        # Migration: Ensure rain_status and rain_level columns exist in SQLite table
        try:
            cur.execute("PRAGMA table_info(sensor_readings);")
            cols = [col[1] for col in cur.fetchall()]
            if "rain_status" not in cols:
                cur.execute("ALTER TABLE sensor_readings ADD COLUMN rain_status TEXT DEFAULT 'No Rain';")
                conn.commit()
            if "rain_level" not in cols:
                cur.execute("ALTER TABLE sensor_readings ADD COLUMN rain_level TEXT DEFAULT 'No Rain';")
                conn.commit()
        except Exception as mig_e:
            logger.warning(f"SQLite migration notice: {mig_e}")

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
