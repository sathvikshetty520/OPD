"""
Production entry point. Run this instead of app.py for any real deployment.
app.py's __main__ block (Flask dev server) stays for local development only.
"""

from waitress import serve
from app import app

if __name__ == "__main__":
    print("Serving on http://0.0.0.0:5000 (production WSGI server)")
    serve(app, host="0.0.0.0", port=5000, threads=4)