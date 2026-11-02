import os
import sys

# Ensure project root and backend folder are in Python path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.app import app

if __name__ == "__main__":
    port_str = os.getenv("PORT") or os.getenv("BACKEND_PORT") or "5000"
    try:
        port = int(port_str)
    except ValueError:
        port = 5000
    app.run(host="0.0.0.0", port=port)
