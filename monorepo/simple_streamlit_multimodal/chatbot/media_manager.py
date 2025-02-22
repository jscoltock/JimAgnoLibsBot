"""
Media storage manager for handling multimodal content.
"""

from pathlib import Path
import shutil
import hashlib
import logging
from typing import Dict, Any

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class MediaManager:
    def __init__(self):
        self.media_dir = Path(__file__).parent.parent / "media_storage"
        self.media_dir.mkdir(exist_ok=True)
        logger.debug(f"Initialized MediaManager with media_dir: {self.media_dir}")
        
    def store_media(self, session_id: str, file_data: dict) -> dict:
        """Store media file and return reference data"""
        session_dir = self.media_dir / session_id
        session_dir.mkdir(exist_ok=True)
        logger.debug(f"Storing media in session directory: {session_dir}")
        
        # Create a unique hash for the file
        file_hash = hashlib.md5(file_data['data']).hexdigest()
        file_ext = Path(file_data['name']).suffix
        stored_path = session_dir / f"{file_hash}{file_ext}"
        logger.debug(f"Generated stored path: {stored_path}")
        
        # Store the file
        with open(stored_path, 'wb') as f:
            f.write(file_data['data'])
        logger.debug(f"File written successfully: {stored_path}")
            
        return {
            'type': file_data['type'],
            'original_name': file_data['name'],
            'stored_path': str(stored_path.relative_to(self.media_dir)),
            'file_hash': file_hash
        }
    
    def get_media_path(self, stored_path: str) -> Path:
        """Get the full path for a stored media file"""
        return self.media_dir / stored_path
    
    def cleanup_session(self, session_id: str) -> None:
        """Remove all media files for a session"""
        session_dir = self.media_dir / session_id
        logger.debug(f"Attempting to cleanup session directory: {session_dir}")
        
        if session_dir.exists():
            logger.debug(f"Session directory exists, contains: {list(session_dir.glob('*'))}")
            try:
                shutil.rmtree(session_dir)
                logger.debug(f"Successfully deleted session directory: {session_dir}")
            except Exception as e:
                logger.error(f"Error deleting session directory: {e}", exc_info=True)
                raise
        else:
            logger.debug(f"Session directory does not exist: {session_dir}")
    
    def cleanup_file(self, stored_path: str) -> None:
        """Remove a specific media file"""
        file_path = self.media_dir / stored_path
        logger.debug(f"Attempting to delete file: {file_path}")
        if file_path.exists():
            try:
                file_path.unlink()
                logger.debug(f"Successfully deleted file: {file_path}")
            except Exception as e:
                logger.error(f"Error deleting file: {e}", exc_info=True)
                raise
        else:
            logger.debug(f"File does not exist: {file_path}")
            
    def serialize_media_ref(self, media_ref: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare media reference for storage"""
        return {
            'type': media_ref['type'],
            'original_name': media_ref['original_name'],
            'stored_path': media_ref['stored_path'],
            'file_hash': media_ref['file_hash']
        } 