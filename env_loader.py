# env_loader.py
from dotenv import load_dotenv, find_dotenv

# Load the nearest .env (repo root). override=False so real env vars win.
load_dotenv(find_dotenv(), override=False)
