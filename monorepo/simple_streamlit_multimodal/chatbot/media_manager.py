"""
Media storage manager for handling multimodal content.
"""

from pathlib import Path
import shutil
import hashlib
from typing import Dict, Any

class MediaManager:
    def __init__(self):
        self.media_dir = Path(__file__).parent.parent / "media_storage"
        self.media_dir.mkdir(exist_ok=True)
        
    def store_media(self, session_id: str, file_data: dict) -> dict:
        """Store media file and return reference data"""
        session_dir = self.media_dir / session_id
        session_dir.mkdir(exist_ok=True)
        
        # Create a unique hash for the file
        file_hash = hashlib.md5(file_data['data']).hexdigest()
        file_ext = Path(file_data['name']).suffix
        stored_path = session_dir / f"{file_hash}{file_ext}"
        
        # Store the file
        with open(stored_path, 'wb') as f:
            f.write(file_data['data'])
            
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
        if session_dir.exists():
            shutil.rmtree(session_dir)
    
    def cleanup_file(self, stored_path: str) -> None:
        """Remove a specific media file"""
        file_path = self.media_dir / stored_path
        if file_path.exists():
            file_path.unlink()
            
    def serialize_media_ref(self, media_ref: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare media reference for storage"""
        return {
            'type': media_ref['type'],
            'original_name': media_ref['original_name'],
            'stored_path': media_ref['stored_path'],
            'file_hash': media_ref['file_hash']
        } 