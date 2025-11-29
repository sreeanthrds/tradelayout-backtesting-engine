"""
Token Manager
Handles storage and retrieval of broker access tokens.
Currently uses file-based storage, can be migrated to Supabase later.
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional, Dict
from pathlib import Path


class TokenManager:
    """
    Manages broker access tokens with file-based storage.
    Supports token expiry tracking and automatic refresh detection.
    """

    def __init__(self, storage_dir: Optional[str] = None):
        """
        Initialize token manager.
        
        Args:
            storage_dir: Directory to store token files (default: ~/.trading_tokens)
        """
        if storage_dir is None:
            storage_dir = os.path.expanduser('~/.trading_tokens')
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_token_file(self, broker: str, user_id: str) -> Path:
        """Get token file path for broker and user."""
        filename = f"{broker}_{user_id}_token.json"
        return self.storage_dir / filename

    def save_token(
        self,
        broker: str,
        user_id: str,
        access_token: str,
        expires_in_seconds: Optional[int] = None,
        additional_data: Optional[Dict] = None
    ) -> bool:
        """
        Save access token to file.
        
        Args:
            broker: Broker name (e.g., 'aliceblue', 'zerodha')
            user_id: User ID
            access_token: Access token string
            expires_in_seconds: Token validity in seconds (None = no expiry)
            additional_data: Any additional data to store (e.g., refresh_token, api_key)
        
        Returns:
            True if saved successfully
        """
        try:
            token_data = {
                'broker': broker,
                'user_id': user_id,
                'access_token': access_token,
                'created_at': datetime.now().isoformat(),
                'expires_at': None,
                'additional_data': additional_data or {}
            }

            if expires_in_seconds:
                expires_at = datetime.now() + timedelta(seconds=expires_in_seconds)
                token_data['expires_at'] = expires_at.isoformat()

            token_file = self._get_token_file(broker, user_id)
            with open(token_file, 'w') as f:
                json.dump(token_data, f, indent=2)

            print(f"✅ Token saved for {broker} user {user_id}")
            return True

        except Exception as e:
            print(f"❌ Error saving token: {e}")
            return False

    def load_token(self, broker: str, user_id: str) -> Optional[Dict]:
        """
        Load access token from file.
        
        Args:
            broker: Broker name
            user_id: User ID
        
        Returns:
            Token data dictionary or None if not found/expired
        """
        try:
            token_file = self._get_token_file(broker, user_id)
            
            if not token_file.exists():
                print(f"ℹ️ No saved token found for {broker} user {user_id}")
                return None

            with open(token_file, 'r') as f:
                token_data = json.load(f)

            # Check expiry
            if token_data.get('expires_at'):
                expires_at = datetime.fromisoformat(token_data['expires_at'])
                if datetime.now() >= expires_at:
                    print(f"⚠️ Token expired for {broker} user {user_id}")
                    return None

            print(f"✅ Token loaded for {broker} user {user_id}")
            return token_data

        except Exception as e:
            print(f"❌ Error loading token: {e}")
            return None

    def get_access_token(self, broker: str, user_id: str) -> Optional[str]:
        """
        Get just the access token string.
        
        Args:
            broker: Broker name
            user_id: User ID
        
        Returns:
            Access token string or None
        """
        token_data = self.load_token(broker, user_id)
        return token_data['access_token'] if token_data else None

    def delete_token(self, broker: str, user_id: str) -> bool:
        """
        Delete saved token.
        
        Args:
            broker: Broker name
            user_id: User ID
        
        Returns:
            True if deleted successfully
        """
        try:
            token_file = self._get_token_file(broker, user_id)
            if token_file.exists():
                token_file.unlink()
                print(f"✅ Token deleted for {broker} user {user_id}")
            return True
        except Exception as e:
            print(f"❌ Error deleting token: {e}")
            return False

    def is_token_valid(self, broker: str, user_id: str) -> bool:
        """
        Check if token exists and is not expired.
        
        Args:
            broker: Broker name
            user_id: User ID
        
        Returns:
            True if token is valid
        """
        token_data = self.load_token(broker, user_id)
        return token_data is not None

    def list_saved_tokens(self) -> list:
        """
        List all saved tokens.
        
        Returns:
            List of (broker, user_id) tuples
        """
        tokens = []
        for token_file in self.storage_dir.glob('*_token.json'):
            try:
                with open(token_file, 'r') as f:
                    data = json.load(f)
                    tokens.append((data['broker'], data['user_id']))
            except:
                continue
        return tokens


# Global instance
_token_manager = None


def get_token_manager() -> TokenManager:
    """Get global token manager instance."""
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenManager()
    return _token_manager
