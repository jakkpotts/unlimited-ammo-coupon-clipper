import os
import json
import logging
import shutil
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self, base_path: str = None):
        """Initialize session manager with base path for session storage"""
        self.base_path = base_path or os.path.join(os.getcwd(), "app", "sessions")
        self._ensure_session_dir()

    def _ensure_session_dir(self):
        """Ensure the session directory exists"""
        os.makedirs(self.base_path, exist_ok=True)

    def get_user_session_dir(self, user_id: int) -> str:
        """Get the session directory for a specific user"""
        return os.path.join(self.base_path, str(user_id))

    def get_store_session_path(self, user_id: int, store_id: int) -> str:
        """Get the session file path for a specific user and store"""
        return os.path.join(self.get_user_session_dir(user_id), f"store_{store_id}_session.json")

    async def save_session(self, user_id: int, store_id: int, session_data: Dict) -> bool:
        """Save a session for a user and store"""
        try:
            session_dir = self.get_user_session_dir(user_id)
            os.makedirs(session_dir, exist_ok=True)
            
            session_path = self.get_store_session_path(user_id, store_id)
            
            # Add metadata to session
            session_data['_metadata'] = {
                'created_at': datetime.utcnow().isoformat(),
                'user_id': user_id,
                'store_id': store_id
            }
            
            with open(session_path, 'w') as f:
                json.dump(session_data, f)
            
            logger.info(f"Saved session for user {user_id} and store {store_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save session: {str(e)}")
            return False

    async def load_session(self, user_id: int, store_id: int) -> Optional[Dict]:
        """Load a session for a user and store if it exists and is valid"""
        try:
            session_path = self.get_store_session_path(user_id, store_id)
            if not os.path.exists(session_path):
                return None
                
            with open(session_path, 'r') as f:
                session_data = json.load(f)
            
            # Check session age
            metadata = session_data.get('_metadata', {})
            created_at = datetime.fromisoformat(metadata.get('created_at', '2000-01-01T00:00:00'))
            
            if datetime.utcnow() - created_at > timedelta(days=7):  # Session expired after 7 days
                logger.info(f"Session expired for user {user_id} and store {store_id}")
                await self.delete_session(user_id, store_id)
                return None
            
            return session_data
            
        except Exception as e:
            logger.error(f"Failed to load session: {str(e)}")
            return None

    async def delete_session(self, user_id: int, store_id: int) -> bool:
        """Delete a specific session"""
        try:
            session_path = self.get_store_session_path(user_id, store_id)
            if os.path.exists(session_path):
                os.remove(session_path)
                logger.info(f"Deleted session for user {user_id} and store {store_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete session: {str(e)}")
            return False

    async def cleanup_expired_sessions(self, max_age_days: int = 7) -> int:
        """Clean up expired sessions older than max_age_days"""
        cleaned_count = 0
        try:
            for user_dir in Path(self.base_path).iterdir():
                if not user_dir.is_dir():
                    continue
                    
                for session_file in user_dir.glob("store_*_session.json"):
                    try:
                        with open(session_file, 'r') as f:
                            session_data = json.load(f)
                        
                        metadata = session_data.get('_metadata', {})
                        created_at = datetime.fromisoformat(metadata.get('created_at', '2000-01-01T00:00:00'))
                        
                        if datetime.utcnow() - created_at > timedelta(days=max_age_days):
                            os.remove(session_file)
                            cleaned_count += 1
                            
                    except Exception as e:
                        logger.warning(f"Error processing session file {session_file}: {str(e)}")
                        continue
                        
                # Remove empty user directories
                if not any(user_dir.iterdir()):
                    shutil.rmtree(user_dir)
                    
            logger.info(f"Cleaned up {cleaned_count} expired sessions")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup sessions: {str(e)}")
            return cleaned_count

    async def rotate_session(self, user_id: int, store_id: int, new_session_data: Dict) -> bool:
        """Rotate a session by safely replacing it with new data"""
        try:
            # Backup existing session
            session_path = self.get_store_session_path(user_id, store_id)
            backup_path = f"{session_path}.bak"
            
            if os.path.exists(session_path):
                shutil.copy2(session_path, backup_path)
            
            # Save new session
            success = await self.save_session(user_id, store_id, new_session_data)
            
            if success and os.path.exists(backup_path):
                os.remove(backup_path)
                
            return success
            
        except Exception as e:
            logger.error(f"Failed to rotate session: {str(e)}")
            # Restore backup if exists
            if os.path.exists(backup_path):
                shutil.move(backup_path, session_path)
            return False 