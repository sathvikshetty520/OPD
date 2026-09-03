"""
Production entry point. Run this instead of app.py for any real deployment.
"""

from waitress import serve
from app import app
import ssl
import socket
from pathlib import Path

CERT_PATH = Path(__file__).parent / "cert.pem"
KEY_PATH = Path(__file__).parent / "key.pem"

if __name__ == "__main__":
    if CERT_PATH.exists() and KEY_PATH.exists():
        # waitress itself doesn't do TLS -- wrap the raw socket instead.
        import waitress.server

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(CERT_PATH), str(KEY_PATH))

        print("Serving on https://0.0.0.0:5000 (self-signed cert)")
        server = waitress.server.create_server(app, host="0.0.0.0", port=5000, threads=4)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        server.run()
    else:
        print("No cert.pem/key.pem found -- falling back to plain HTTP.")
        print("Serving on http://0.0.0.0:5000 (production WSGI server)")
        serve(app, host="0.0.0.0", port=5000, threads=4)