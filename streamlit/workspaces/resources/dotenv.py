from dotenv import load_dotenv
import os


def load_environment(env_file: str | None = None):
    """Load environment variables from a .env file."""
    if env_file:
        os.environ["OPENAGRI_ENV_FILE"] = env_file

    configured_env_file = os.environ.get("OPENAGRI_ENV_FILE")

    if configured_env_file and os.path.exists(configured_env_file):
        load_dotenv(configured_env_file)
    elif os.path.exists("/env/.env"):
        load_dotenv("/env/.env")
    elif os.path.exists(".env.testing"):
        print("!!! Loading environment variables from .env.testing !!!")
        load_dotenv(".env.testing")
    else:
        load_dotenv(".env")
    return True
