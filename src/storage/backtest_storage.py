"""
Backtest Storage Module
Handles file-based storage of backtest results with compression
"""
import gzip
import json
import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta, date, time
from typing import Dict, Any, List, Optional

class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects"""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, time):
            return obj.isoformat()
        elif isinstance(obj, timedelta):
            return str(obj.total_seconds())
        return super().default(obj)


class BacktestStorage:
    """Manages file-based storage for backtest results"""
    
    def __init__(self, base_path: str = "backtest_data"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
    
    def get_user_folder(self, user_id: str) -> Path:
        """Get user folder path"""
        folder = self.base_path / user_id
        folder.mkdir(exist_ok=True)
        return folder
    
    def get_strategy_folder(self, user_id: str, strategy_id: str) -> Path:
        """Get strategy folder path"""
        folder = self.get_user_folder(user_id) / strategy_id
        folder.mkdir(exist_ok=True)
        return folder
    
    def clear_strategy_data(self, user_id: str, strategy_id: str) -> Dict[str, Any]:
        """Clear all data for a strategy"""
        strategy_folder = self.get_strategy_folder(user_id, strategy_id)
        
        # Count files and calculate size
        file_count = 0
        total_size = 0
        
        if strategy_folder.exists():
            for file in strategy_folder.glob("*.json.gz"):
                total_size += file.stat().st_size
                file_count += 1
            
            # Also count metadata
            metadata_file = strategy_folder / "metadata.json"
            if metadata_file.exists():
                total_size += metadata_file.stat().st_size
            
            # Remove entire folder
            shutil.rmtree(strategy_folder)
            
            # Recreate empty folder
            strategy_folder.mkdir(exist_ok=True)
        
        return {
            "deleted_files": file_count,
            "freed_space_mb": round(total_size / (1024 * 1024), 2)
        }
    
    def save_metadata(self, user_id: str, strategy_id: str, metadata: Dict[str, Any]) -> None:
        """Save backtest metadata"""
        strategy_folder = self.get_strategy_folder(user_id, strategy_id)
        metadata_file = strategy_folder / "metadata.json"
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, cls=DateTimeEncoder)
    
    def load_metadata(self, user_id: str, strategy_id: str) -> Optional[Dict[str, Any]]:
        """Load backtest metadata"""
        strategy_folder = self.get_strategy_folder(user_id, strategy_id)
        metadata_file = strategy_folder / "metadata.json"
        
        if not metadata_file.exists():
            return None
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def save_day_data(self, user_id: str, strategy_id: str, date: str, day_data: Dict[str, Any]) -> None:
        """
        Save compressed day data
        
        Args:
            user_id: User ID
            strategy_id: Strategy ID
            date: Date in DD-MM-YYYY format
            day_data: Dictionary containing summary and positions
        """
        strategy_folder = self.get_strategy_folder(user_id, strategy_id)
        day_file = strategy_folder / f"{date}.json.gz"
        
        # Write compressed JSON with custom encoder
        with gzip.open(day_file, 'wt', encoding='utf-8') as f:
            json.dump(day_data, f, cls=DateTimeEncoder, indent=2)
    
    def load_day_data(self, user_id: str, strategy_id: str, date: str) -> Optional[Dict[str, Any]]:
        """
        Load compressed day data
        
        Args:
            user_id: User ID
            strategy_id: Strategy ID
            date: Date in DD-MM-YYYY format
        
        Returns:
            Dictionary with day data or None if not found
        """
        strategy_folder = self.get_strategy_folder(user_id, strategy_id)
        day_file = strategy_folder / f"{date}.json.gz"
        
        if not day_file.exists():
            return None
        
        # Read compressed JSON
        with gzip.open(day_file, 'rt', encoding='utf-8') as f:
            return json.load(f)
    
    def get_day_file_path(self, user_id: str, strategy_id: str, date: str) -> Optional[Path]:
        """Get the Path to the compressed day file without reading it.
        
        Args:
            user_id: User ID
            strategy_id: Strategy ID
            date: Date in DD-MM-YYYY format
        
        Returns:
            Path object for the gzipped JSON file, or None if it does not exist
        """
        strategy_folder = self.get_strategy_folder(user_id, strategy_id)
        day_file = strategy_folder / f"{date}.json.gz"
        if not day_file.exists():
            return None
        return day_file
    
    def list_dates(self, user_id: str, strategy_id: str) -> List[Dict[str, Any]]:
        """List all available dates with file sizes"""
        strategy_folder = self.get_strategy_folder(user_id, strategy_id)
        
        dates = []
        for file in sorted(strategy_folder.glob("*.json.gz")):
            date_str = file.stem  # Remove .json.gz
            file_size = file.stat().st_size
            
            dates.append({
                "date": date_str,
                "file_size_kb": round(file_size / 1024, 2),
                "file_path": str(file)
            })
        
        return dates
    
    def cleanup_expired(self, ttl_hours: int = 12) -> Dict[str, Any]:
        """
        Clean up expired backtest data
        
        Args:
            ttl_hours: Time to live in hours
        
        Returns:
            Summary of cleanup
        """
        cutoff_time = datetime.now() - timedelta(hours=ttl_hours)
        
        deleted_strategies = 0
        freed_space = 0
        
        # Scan all user folders
        for user_folder in self.base_path.iterdir():
            if not user_folder.is_dir():
                continue
            
            # Scan strategy folders
            for strategy_folder in user_folder.iterdir():
                if not strategy_folder.is_dir():
                    continue
                
                metadata_file = strategy_folder / "metadata.json"
                
                if not metadata_file.exists():
                    continue
                
                # Check creation time
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                created_at_str = metadata.get('created_at')
                if not created_at_str:
                    continue
                
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                
                # If expired, delete
                if created_at < cutoff_time:
                    # Calculate size
                    folder_size = sum(
                        f.stat().st_size 
                        for f in strategy_folder.glob("**/*") 
                        if f.is_file()
                    )
                    
                    # Delete folder
                    shutil.rmtree(strategy_folder)
                    
                    deleted_strategies += 1
                    freed_space += folder_size
        
        return {
            "deleted_strategies": deleted_strategies,
            "freed_space_mb": round(freed_space / (1024 * 1024), 2),
            "cutoff_time": cutoff_time.isoformat()
        }
    
    def get_file_size(self, user_id: str, strategy_id: str, date: str) -> int:
        """Get file size in bytes"""
        strategy_folder = self.get_strategy_folder(user_id, strategy_id)
        day_file = strategy_folder / f"{date}.json.gz"
        
        if not day_file.exists():
            return 0
        
        return day_file.stat().st_size
    
    def strategy_exists(self, user_id: str, strategy_id: str) -> bool:
        """Check if strategy data exists"""
        strategy_folder = self.get_strategy_folder(user_id, strategy_id)
        metadata_file = strategy_folder / "metadata.json"
        return metadata_file.exists()


# Singleton instance
_storage_instance = None

def get_storage() -> BacktestStorage:
    """Get singleton storage instance"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = BacktestStorage()
    return _storage_instance
