"""Generate the TRES_COMAS_PASSWORD_HASH value for the production .env.

Job: prompt for the login password twice (no echo) and print the encoded scrypt
hash. Paste it into the production .env by hand; this script writes no file and
the plain password is never stored (INV-3).

Usage: ``python hash_password.py``
"""

import getpass
import sys

from app.services.auth import hash_password

MIN_LENGTH = 12


def main() -> int:
    """Prompt, validate and print the hash. Returns a process exit code."""
    password = getpass.getpass("Password: ")
    if len(password) < MIN_LENGTH:
        print(f"Refusing: password must be at least {MIN_LENGTH} characters.", file=sys.stderr)
        return 1
    if getpass.getpass("Repeat password: ") != password:
        print("Refusing: passwords do not match.", file=sys.stderr)
        return 1
    print(f"TRES_COMAS_PASSWORD_HASH={hash_password(password)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
