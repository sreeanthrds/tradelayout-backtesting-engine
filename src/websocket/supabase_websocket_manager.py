"""
WebSocket Manager with Supabase Real-time Integration
Handles WebSocket connections and forwards Supabase real-time updates to clients
"""
import asyncio
import json
import logging
from typing import Dict, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect
from src.services.supabase_realtime_service import get_supabase_service

logger = logging.getLogger(__name__)


class SupabaseWebSocketManager:
    """
    Manages WebSocket connections and subscribes to Supabase real-time updates
    
    Flow:
    1. Users connect via WebSocket
    2. Manager subscribes to Supabase real-time (once)
    3. When Supabase pushes update, manager forwards to relevant user
    """
    
    def __init__(self):
        # Store active connections: {user_id: WebSocket}
        self.active_connections: Dict[str, WebSocket] = {}
        
        # Store session to user mapping: {session_id: user_id}
        self.session_to_user: Dict[str, str] = {}
        
        # Supabase service
        self.supabase = get_supabase_service()
        
        # Subscription status
        self.subscribed = False
        
        logger.info("✅ SupabaseWebSocketManager initialized")
    
    async def start(self):
        """Start the WebSocket manager and subscribe to Supabase"""
        if not self.subscribed:
            await self._subscribe_to_supabase()
            self.subscribed = True
            logger.info("✅ Subscribed to Supabase real-time")
    
    async def _subscribe_to_supabase(self):
        """
        Subscribe to Supabase real-time updates
        This is called ONCE when the manager starts
        """
        try:
            # Subscribe to live_sessions table updates
            self.supabase.client.channel('live_sessions').on(
                'postgres_changes',
                {
                    'event': 'UPDATE',
                    'schema': 'public',
                    'table': 'live_sessions'
                },
                self._handle_supabase_update
            ).subscribe()
            
            logger.info("✅ Subscribed to Supabase live_sessions updates")
            
        except Exception as e:
            logger.error(f"❌ Error subscribing to Supabase: {e}")
            raise
    
    async def _handle_supabase_update(self, payload):
        """
        Called when Supabase pushes an update
        Forwards the update to the relevant user's WebSocket
        """
        try:
            updated_session = payload.get('new', {})
            session_id = updated_session.get('id')
            user_id = updated_session.get('user_id')
            
            if not session_id or not user_id:
                logger.warning(f"⚠️ Received update without session_id or user_id: {payload}")
                return
            
            logger.debug(f"📥 Supabase update for session {session_id}, user {user_id}")
            
            # Find user's WebSocket and send update
            if user_id in self.active_connections:
                websocket = self.active_connections[user_id]
                
                # Send update to user
                await websocket.send_json({
                    'type': 'session_update',
                    'data': updated_session,
                    'timestamp': updated_session.get('updated_at')
                })
                
                logger.debug(f"📤 Pushed update to user {user_id}")
            else:
                logger.debug(f"ℹ️ User {user_id} not connected, skipping update")
                
        except Exception as e:
            logger.error(f"❌ Error handling Supabase update: {e}")
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """
        Accept a new WebSocket connection from a user
        
        Args:
            websocket: The WebSocket connection
            user_id: The user's ID (from Clerk JWT)
        """
        try:
            await websocket.accept()
            self.active_connections[user_id] = websocket
            
            logger.info(f"✅ User {user_id} connected. Total connections: {len(self.active_connections)}")
            
            # Send initial data for all user's sessions
            sessions = self.supabase.get_active_sessions(user_id)
            
            await websocket.send_json({
                'type': 'initial_data',
                'data': sessions,
                'timestamp': None
            })
            
            logger.info(f"📤 Sent initial data to user {user_id}: {len(sessions)} sessions")
            
        except Exception as e:
            logger.error(f"❌ Error connecting user {user_id}: {e}")
            raise
    
    async def disconnect(self, user_id: str):
        """
        Disconnect a user's WebSocket
        
        Args:
            user_id: The user's ID
        """
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"❌ User {user_id} disconnected. Total connections: {len(self.active_connections)}")
        
        # Clean up session mappings
        sessions_to_remove = [
            session_id for session_id, uid in self.session_to_user.items() 
            if uid == user_id
        ]
        for session_id in sessions_to_remove:
            del self.session_to_user[session_id]
    
    async def broadcast_to_user(self, user_id: str, message: Dict):
        """
        Send a message to a specific user
        
        Args:
            user_id: The user's ID
            message: The message to send
        """
        if user_id in self.active_connections:
            try:
                websocket = self.active_connections[user_id]
                await websocket.send_json(message)
                logger.debug(f"📤 Sent message to user {user_id}")
            except Exception as e:
                logger.error(f"❌ Error sending to user {user_id}: {e}")
                await self.disconnect(user_id)
    
    async def broadcast_to_all(self, message: Dict):
        """
        Broadcast a message to all connected users
        
        Args:
            message: The message to send
        """
        disconnected_users = []
        
        for user_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"❌ Error broadcasting to user {user_id}: {e}")
                disconnected_users.append(user_id)
        
        # Clean up disconnected users
        for user_id in disconnected_users:
            await self.disconnect(user_id)
    
    def get_connection_count(self) -> int:
        """Get the number of active connections"""
        return len(self.active_connections)
    
    def is_user_connected(self, user_id: str) -> bool:
        """Check if a user is connected"""
        return user_id in self.active_connections


# Singleton instance
_ws_manager = None

def get_websocket_manager() -> SupabaseWebSocketManager:
    """Get or create WebSocket manager instance"""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = SupabaseWebSocketManager()
    return _ws_manager
