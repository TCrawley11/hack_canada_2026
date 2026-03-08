import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv

load_dotenv()

from .deterrent import trigger_deterrent, SCRIPTS
from .incidents import log_incident, get_incidents
from .threats import record_threat, get_threat_summary

app = FastAPI(title="FarmGuardian")


@app.get("/")
def read_root():
    return {"message": "SOY SCARECROW API is running"}


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
            await websocket.send_json({
                "triggered": True,
                "species": species,
                "script": script,
                "timestamp": incident["timestamp"],
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
