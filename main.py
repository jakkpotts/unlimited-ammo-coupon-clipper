from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import auth, stores, coupons
from app.db.base import Base, engine
from app.core.tasks import cleanup_sessions_task
import logging
from dotenv import load_dotenv
import os
from pathlib import Path
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the absolute path to the .env file
env_path = Path(__file__).parent / '.env'
logger.info(f"Looking for .env file at: {env_path}")

# Load environment variables from specific path
if env_path.exists():
    logger.info(f".env file found")
    # Read and log the raw contents (excluding sensitive data)
    with open(env_path) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key = line.split('=')[0].strip()
                if 'KEY' not in key.upper() and 'SECRET' not in key.upper():
                    logger.info(f"Raw line: {line.strip()}")
    
    load_dotenv(dotenv_path=env_path)
else:
    logger.error(f".env file not found at {env_path}")
    raise RuntimeError(".env file not found")

# Verify environment variables are loaded
logger.info("Checking environment variables...")
required_vars = ["AGENTQL_API_KEY", "AGENTQL_ENVIRONMENT", "AGENTQL_TIMEOUT"]
for var in required_vars:
    value = os.getenv(var)
    if value is None:
        logger.error(f"Missing required environment variable: {var}")
        raise RuntimeError(f"Missing required environment variable: {var}")
    else:
        # Don't log API key value
        if var == "AGENTQL_API_KEY":
            logger.info(f"{var}: {'*' * len(value)}")
        else:
            logger.info(f"{var}: {value}")

app = FastAPI(
    title="Unlimited Ammo Coupon Clipper",
    description="Automated coupon clipping service with user authentication",
    version="1.0.0"
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(stores.router)
app.include_router(coupons.router)

@app.on_event("startup")
async def startup_event():
    """Start background tasks on application startup"""
    # Start session cleanup task
    asyncio.create_task(cleanup_sessions_task())
    logger.info("Started session cleanup background task")

@app.on_event("startup")
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "Coupon Clipper API",
        "version": "1.0.0"
    } 