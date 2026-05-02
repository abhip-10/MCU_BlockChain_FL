from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature, encode_dss_signature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.exceptions import InvalidSignature


def generate_keypair() -> tuple:
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_key, public_key_pem


def sign(private_key, data: bytes) -> bytes:
    return private_key.sign(data, ec.ECDSA(hashes.SHA256()))


def verify(public_key_pem: bytes, data: bytes, signature: bytes) -> bool:
    try:
        public_key = serialization.load_pem_public_key(public_key_pem)
        public_key.verify(signature, data, ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, Exception):
        return False
