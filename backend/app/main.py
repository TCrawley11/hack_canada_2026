from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from .deterrent import trigger_deterrent, SCRIPTS
from .incidents import log_incident, get_incidents

app = FastAPI(title="FarmGuardian")


class DetectionEvent(BaseModel):
    species: str
    confidence: float | None = None


@app.get("/")
def read_root():
    return {"message": "FarmGuardian API is running"}


@app.post("/detection")
def handle_detection(event: DetectionEvent):
    """
    Called by the ML model when a pest is detected.
    Triggers ElevenLabs audio for the detected species if not on cooldown.
    """
    species = event.species.lower()
    script = trigger_deterrent(species)

    if script is None:
        return {
            "triggered": False,
            "reason": "cooldown active",
            "species": species,
        }

    incident = log_incident(species=species, script=script)
    return {
        "triggered": True,
        "species": species,
        "script": script,
        "confidence": event.confidence,
        "timestamp": incident["timestamp"],
    }


@app.get("/incidents")
def incidents():
    """Return the last 20 detection incidents."""
    return get_incidents()


@app.get("/species")
def supported_species():
    """Return the list of species the deterrent system knows about."""
    return {"species": list(SCRIPTS.keys())}
