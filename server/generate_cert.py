
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import datetime

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, u'opd-triage-server')])
cert = x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(
    key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(
    datetime.datetime.utcnow()).not_valid_after(
    datetime.datetime.utcnow() + datetime.timedelta(days=825)).add_extension(
    x509.SubjectAlternativeName([x509.DNSName(u'localhost'), x509.IPAddress(__import__('ipaddress').ip_address(u'192.168.1.104'))]),
    critical=False).sign(key, hashes.SHA256())

with open('cert.pem', 'wb') as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))
with open('key.pem', 'wb') as f:
    f.write(key.private_bytes(encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()))
print('cert.pem and key.pem created')
