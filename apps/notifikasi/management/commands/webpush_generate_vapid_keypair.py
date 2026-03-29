"""
Generate VAPID keypair for Web Push (django-webpush).
Add keys to .env: VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY
"""
from django.core.management.base import BaseCommand


def generate_vapid_keypair():
    """Generate VAPID keys, returns (public_key, private_key) as base64url strings."""
    try:
        from webpush.vapid import get_vapid_keypair
        return get_vapid_keypair()
    except ImportError:
        pass

    # Fallback: generate using cryptography (same format as webpush)
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    import base64

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

    return b64url_encode(pub_bytes), b64url_encode(priv_bytes)


class Command(BaseCommand):
    help = "Generate VAPID public/private keypair for Web Push notifications"

    def handle(self, *args, **options):
        try:
            public_key, private_key = generate_vapid_keypair()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error generating keys: {e}"))
            return

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("VAPID keys generated. Add to your .env file:"))
        self.stdout.write("")
        self.stdout.write(f"VAPID_PUBLIC_KEY={public_key}")
        self.stdout.write(f"VAPID_PRIVATE_KEY={private_key}")
        self.stdout.write("VAPID_ADMIN_EMAIL=admin@example.com")
        self.stdout.write("")
