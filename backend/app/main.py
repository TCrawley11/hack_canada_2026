import json
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from .deterrent import trigger_deterrent, SCRIPTS
from .incidents import log_incident, get_incidents
from .threats import record_threat, get_threat_summary

app = FastAPI(title="FarmGuardian")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store connected frontend clients
frontend_clients: List[WebSocket] = []


async def broadcast_to_frontend(event: dict):
    """Broadcast detection event to all connected frontend clients."""
    disconnected = []
    for client in frontend_clients:
        try:
            await client.send_json(event)
        except:
            disconnected.append(client)
    for client in disconnected:
        frontend_clients.remove(client)


@app.get("/")
def read_root():
    return {"message": "SOY SCARECROW API is running"}


@app.websocket("/ws/events")
async def ws_events(websocket: WebSocket):
    """
    WebSocket endpoint for frontend dashboard.
    Receives detection events and displays them in the detection log.
    """
    await websocket.accept()
    frontend_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in frontend_clients:
            frontend_clients.remove(websocket)


@app.websocket("/ws/detection")
async def ws_detection(websocket: WebSocket):
    """
    WebSocket endpoint for the ML model.
    Receives continuous detection frames and triggers ElevenLabs deterrent when threatening.
    """
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            species = str(data.get("species", "")).lower()
            threatening = bool(data.get("threatening", False))
            confidence = float(data.get("confidence", 0.0))
            timestamp = data.get("timestamp", "")

            if not threatening:
                await websocket.send_json({
                    "triggered": False,
                    "reason": "not threatening",
                    "species": species,
                })
                continue

            script = trigger_deterrent(species)

            if script is None:
                await websocket.send_json({
                    "triggered": False,
                    "reason": "cooldown active",
                    "species": species,
                })
                continue

            incident = log_incident(species=species, script=script)
            record_threat(species)
            
            response = {
                "triggered": True,
                "species": species,
                "script": script,
                "timestamp": incident["timestamp"],
            }
            await websocket.send_json(response)
            
            # Broadcast to frontend dashboard
            await broadcast_to_frontend({
                "type": "detection",
                "species": species,
                "confidence": confidence,
                "scare": script,
                "timestamp": timestamp,
            })

    except WebSocketDisconnect:
        pass


@app.get("/incidents")
def incidents():
    """Return the last 20 detection incidents."""
    return get_incidents()


@app.get("/threats")
def threat_summary():
    """Return all detected threat species sorted by frequency."""
    return get_threat_summary()


@app.get("/species")
def supported_species():
    """Return the list of species the deterrent system knows about."""
    return {"species": list(SCRIPTS.keys())}
