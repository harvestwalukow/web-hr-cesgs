#!/usr/bin/env python
"""
Generate VAPID keys for Web Push. Tidak perlu Django.
Jalankan: python scripts/generate_vapid_keys.py
Tambahkan output ke .env
"""
import base64
import sys

try:
    from webpush.vapid import get_vapid_keypair
    public_key, private_key = get_vapid_keypair()
except ImportError:
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization

        def b64url_encode(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')

        private_key_obj = ec.generate_private_key(ec.SECP256R1())
        public_key_obj = private_key_obj.public_key()

        pub_bytes = public_key_obj.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )
        priv_val = private_key_obj.private_numbers().private_value
        priv_bytes = priv_val.to_bytes(32, 'big')

        public_key = b64url_encode(pub_bytes)
        private_key = b64url_encode(priv_bytes)
    except ImportError as e:
        print("Error: Install dependencies: pip install django-webpush (or cryptography)", file=sys.stderr)
        sys.exit(1)

print("\nVAPID keys generated. Add to your .env file:\n")
print(f"VAPID_PUBLIC_KEY={public_key}")
print(f"VAPID_PRIVATE_KEY={private_key}")
print("VAPID_ADMIN_EMAIL=admin@example.com")
print()
