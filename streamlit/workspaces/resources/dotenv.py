from dotenv import load_dotenv
import os

def load_environment():
    """Load environment variables from a .env file."""
    if os.path.exists("/env/.env"):
        load_dotenv("/env/.env")
    else:
        load_dotenv(".env")
    return True