import asyncio
import logging
from datetime import datetime, timedelta
from app.services.session_manager import SessionManager

logger = logging.getLogger(__name__)

async def cleanup_sessions_task():
    """Background task to periodically clean up expired sessions"""
    session_manager = SessionManager()
    
    while True:
        try:
            logger.info("Starting session cleanup task")
            cleaned_count = await session_manager.cleanup_expired_sessions()
            logger.info(f"Session cleanup complete. Removed {cleaned_count} expired sessions")
            
            # Wait for 24 hours before next cleanup
            await asyncio.sleep(24 * 60 * 60)
            
        except Exception as e:
            logger.error(f"Error in session cleanup task: {str(e)}")
            # Wait for 1 hour before retry on error
            await asyncio.sleep(60 * 60) 