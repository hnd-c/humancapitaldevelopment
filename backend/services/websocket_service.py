#!/usr/bin/env python3
"""
WebSocket Service - Real-time updates for UMAP visualization

This service handles:
- WebSocket connection management
- Real-time student progress notifications
- UMAP visualization updates
- Connection lifecycle management
"""

import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)


@dataclass
class StudentConnection:
    """Individual student WebSocket connection"""
    websocket: WebSocket
    student_id: str
    connected_at: datetime
    last_ping: datetime


class WebSocketManager:
    """Manages WebSocket connections for real-time UMAP updates"""

    def __init__(self):
        # Active connections by student_id
        self.active_connections: Dict[str, List[StudentConnection]] = {}
        # Connection health monitoring
        self._ping_interval = 30  # seconds
        self._connection_timeout = 60  # seconds

    async def connect(self, websocket: WebSocket, student_id: str) -> bool:
        """Accept WebSocket connection and add to active connections"""
        try:
            await websocket.accept()

            connection = StudentConnection(
                websocket=websocket,
                student_id=student_id,
                connected_at=datetime.now(),
                last_ping=datetime.now()
            )

            if student_id not in self.active_connections:
                self.active_connections[student_id] = []

            self.active_connections[student_id].append(connection)

            logger.info(f"WebSocket connected for student {student_id}")

            # Send welcome message
            await self._send_to_connection(connection, {
                "type": "connection_established",
                "student_id": student_id,
                "timestamp": time.time(),
                "message": "Real-time UMAP updates enabled"
            })

            return True

        except Exception as e:
            logger.error(f"Failed to establish WebSocket connection for student {student_id}: {e}")
            return False

    def disconnect(self, websocket: WebSocket, student_id: str):
        """Remove WebSocket connection"""
        try:
            if student_id in self.active_connections:
                # Remove the specific websocket connection
                self.active_connections[student_id] = [
                    conn for conn in self.active_connections[student_id]
                    if conn.websocket != websocket
                ]

                # Clean up empty connection lists
                if not self.active_connections[student_id]:
                    del self.active_connections[student_id]

                logger.info(f"WebSocket disconnected for student {student_id}")

        except Exception as e:
            logger.error(f"Error during WebSocket disconnect for student {student_id}: {e}")

    async def send_status_update(
        self,
        student_id: str,
        question_id: str,
        new_status: str,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """Send question status update to student's WebSocket connections"""

        if student_id not in self.active_connections:
            logger.debug(f"No active WebSocket connections for student {student_id}")
            return

        update_message = {
            "type": "question_status_update",
            "question_id": question_id,
            "new_status": new_status,
            "timestamp": time.time(),
            **(additional_data or {})
        }

        await self._send_to_student(student_id, update_message)

    async def send_umap_refresh(self, student_id: str):
        """Notify student that UMAP data should be refreshed"""

        refresh_message = {
            "type": "umap_refresh_needed",
            "student_id": student_id,
            "timestamp": time.time(),
            "message": "UMAP visualization data has been updated"
        }

        await self._send_to_student(student_id, refresh_message)

    async def broadcast_system_update(self, message: Dict[str, Any]):
        """Broadcast system-wide updates to all connected students"""

        system_message = {
            "type": "system_update",
            "timestamp": time.time(),
            **message
        }

        for student_id in list(self.active_connections.keys()):
            await self._send_to_student(student_id, system_message)

    async def handle_ping(self, student_id: str, websocket: WebSocket):
        """Handle ping messages to keep connection alive"""

        if student_id in self.active_connections:
            for connection in self.active_connections[student_id]:
                if connection.websocket == websocket:
                    connection.last_ping = datetime.now()
                    break

        # Send pong response
        pong_message = {
            "type": "pong",
            "timestamp": time.time()
        }

        try:
            await websocket.send_text(json.dumps(pong_message))
        except Exception as e:
            logger.error(f"Failed to send pong to student {student_id}: {e}")

    async def handle_message(self, student_id: str, websocket: WebSocket, message: str):
        """Handle incoming WebSocket messages"""

        try:
            data = json.loads(message)
            message_type = data.get("type")

            if message_type == "ping":
                await self.handle_ping(student_id, websocket)

            elif message_type == "request_status_update":
                # Student requesting specific question status
                question_id = data.get("question_id")
                if question_id:
                    await self._handle_status_request(student_id, question_id, websocket)

            elif message_type == "viewport_change":
                # Student changed viewport (for potential optimization)
                await self._handle_viewport_change(student_id, data, websocket)

            else:
                logger.warning(f"Unknown WebSocket message type: {message_type}")

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON message from student {student_id}: {message}")
        except Exception as e:
            logger.error(f"Error handling WebSocket message from student {student_id}: {e}")

    async def cleanup_stale_connections(self):
        """Remove stale connections that haven't pinged recently"""

        current_time = datetime.now()
        stale_students = []

        for student_id, connections in self.active_connections.items():
            active_connections = []

            for connection in connections:
                time_since_ping = (current_time - connection.last_ping).total_seconds()

                if time_since_ping > self._connection_timeout:
                    logger.info(f"Removing stale WebSocket connection for student {student_id}")
                    try:
                        await connection.websocket.close()
                    except Exception:
                        pass  # Connection might already be closed
                else:
                    active_connections.append(connection)

            if active_connections:
                self.active_connections[student_id] = active_connections
            else:
                stale_students.append(student_id)

        # Remove students with no active connections
        for student_id in stale_students:
            del self.active_connections[student_id]

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics"""

        total_connections = sum(len(conns) for conns in self.active_connections.values())

        return {
            "total_students": len(self.active_connections),
            "total_connections": total_connections,
            "average_connections_per_student": (
                total_connections / len(self.active_connections)
                if self.active_connections else 0
            ),
            "students_with_connections": list(self.active_connections.keys())
        }

    async def _send_to_student(self, student_id: str, message: Dict[str, Any]):
        """Send message to all connections for a specific student"""

        if student_id not in self.active_connections:
            return

        message_json = json.dumps(message)
        failed_connections = []

        for connection in self.active_connections[student_id]:
            try:
                await connection.websocket.send_text(message_json)
            except Exception as e:
                logger.error(f"Failed to send message to student {student_id}: {e}")
                failed_connections.append(connection)

        # Remove failed connections
        if failed_connections:
            self.active_connections[student_id] = [
                conn for conn in self.active_connections[student_id]
                if conn not in failed_connections
            ]

            if not self.active_connections[student_id]:
                del self.active_connections[student_id]

    async def _send_to_connection(self, connection: StudentConnection, message: Dict[str, Any]):
        """Send message to a specific connection"""

        try:
            message_json = json.dumps(message)
            await connection.websocket.send_text(message_json)
        except Exception as e:
            logger.error(f"Failed to send message to connection: {e}")
            raise

    async def _handle_status_request(self, student_id: str, question_id: str, websocket: WebSocket):
        """Handle request for specific question status"""

        # This would integrate with the UMAP service to get current status
        # For now, send acknowledgment
        response = {
            "type": "status_request_received",
            "question_id": question_id,
            "timestamp": time.time()
        }

        try:
            await websocket.send_text(json.dumps(response))
        except Exception as e:
            logger.error(f"Failed to send status request response: {e}")

    async def _handle_viewport_change(self, student_id: str, data: Dict[str, Any], websocket: WebSocket):
        """Handle viewport change notification"""

        # Could be used for spatial optimization in the future
        logger.debug(f"Viewport change for student {student_id}: {data}")

        # Send acknowledgment
        response = {
            "type": "viewport_change_acknowledged",
            "timestamp": time.time()
        }

        try:
            await websocket.send_text(json.dumps(response))
        except Exception as e:
            logger.error(f"Failed to send viewport change response: {e}")


# Global WebSocket manager instance
websocket_manager = WebSocketManager()


class UMAPNotificationService:
    """Service to handle UMAP-specific notifications"""

    def __init__(self, websocket_manager: WebSocketManager):
        self.websocket_manager = websocket_manager

    async def notify_question_answered(
        self,
        student_id: str,
        question_id: str,
        is_correct: bool,
        status: str,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """Notify when a student answers a question"""

        update_data = {
            "is_correct": is_correct,
            "status": status,
            **(additional_data or {})
        }

        await self.websocket_manager.send_status_update(
            student_id=student_id,
            question_id=question_id,
            new_status=status,
            additional_data=update_data
        )

    async def notify_student_progress_batch(
        self,
        student_id: str,
        updates: List[Dict[str, Any]]
    ):
        """Notify multiple question updates at once"""

        batch_message = {
            "type": "batch_status_update",
            "updates": updates,
            "timestamp": time.time()
        }

        await self.websocket_manager._send_to_student(student_id, batch_message)

    async def notify_system_maintenance(self, message: str, duration_minutes: Optional[int] = None):
        """Notify all users of system maintenance"""

        maintenance_message = {
            "type": "system_maintenance",
            "message": message,
            "duration_minutes": duration_minutes,
            "timestamp": time.time()
        }

        await self.websocket_manager.broadcast_system_update(maintenance_message)


# Global notification service instance
umap_notification_service = UMAPNotificationService(websocket_manager)
