"""Run this once to generate the value for QUERIFY_APP_PASSWORD_HASH."""
import getpass

import bcrypt

password = getpass.getpass("Choose a password: ")
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
print("\nAdd this to your .env file:\n")
print(f"QUERIFY_APP_PASSWORD_HASH={hashed}")
