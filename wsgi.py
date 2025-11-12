import os
from pathlib import Path
from dotenv import load_dotenv

# Explicitly load .env from the project root directory
# This ensures gunicorn workers can find it regardless of working directory
base_dir = Path(__file__).resolve().parent
env_path = base_dir / ".env"
if env_path.exists():
    # CRITICAL: Use override=True and explicitly set in os.environ
    # This ensures the environment variable is available to all code
    load_dotenv(env_path, override=True)
    # Double-check: if DATABASE_URL is in the .env file, ensure it's in os.environ
    # This is a safety net for gunicorn workers
    if not os.getenv("DATABASE_URL"):
        # Re-read from .env file directly as fallback
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    if key.strip() == "DATABASE_URL" and not os.getenv("DATABASE_URL"):
                        os.environ["DATABASE_URL"] = value.strip()
else:
    # Fallback to default behavior
    load_dotenv(override=True)

from app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)

