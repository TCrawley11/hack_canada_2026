"""
FarmGuardian – two-stage predator detection pipeline
Stage 1: YOLO11n  →  locate targets in frame (fast, CPU-friendly)
Stage 2: Gemini Vision  →  classify ROI and decide if threatening

MJPEG stream available at http://localhost:8001/stream
"""

import argparse
import json
import os
import re
import time
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO

import cv2
from google import genai
from google.genai import types
from dotenv import load_dotenv
from PIL import Image
from ultralytics import YOLO
from websockets.sync.client import connect as ws_connect

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TARGET_CLASS_IDS = {0, 14, 15, 16, 21}
# 0=person, 14=bird, 15=cat, 16=dog, 21=bear

COCO_NAMES = {0: "person", 14: "bird", 15: "cat", 16: "dog", 21: "bear"}

YOLO_CONF_THRESHOLD = 0.25
GEMINI_CONF_THRESHOLD = 0.6
COOLDOWN_SECONDS = 15
SAMPLE_EVERY_N_FRAMES = 30   # run YOLO every N frames (~2 fps at 30 fps)

GEMINI_PROMPT = (
    "What animal or person is this? If it is a predatory or farm-threatening animal or human "
    "(e.g., human, dog, coyote, wolf, fox, bear, hawk, eagle, raccoon, crow, rat, deer, wild boar), "
    'respond with JSON: {"species": "<name>", "threatening": true/false, "confidence": 0.0-1.0}. '
    'If you cannot identify it or it\'s not a target, return {"threatening": false}.'
)

DEFAULT_WS_URL = "ws://localhost:8000/ws/detection"
DEFAULT_STREAM_PORT = 8001

# Box colours
COLOR_UNCLASSIFIED = (0, 255, 255)  # yellow  — YOLO only, Gemini pending
COLOR_SAFE         = (0, 255, 0)    # green   — Gemini: not threatening
COLOR_THREAT       = (0, 0, 255)    # red     — Gemini: threatening

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

_frame_lock = threading.Lock()
_latest_annotated: bytes = b""

_gemini_lock = threading.Lock()
_gemini_results: dict[int, dict] = {}  # cls_id → last Gemini result
_gemini_pending: set[int] = set()  # cls_ids with pending Gemini calls
_gemini_last_call: dict[int, float] = {}  # cls_id → last call timestamp
GEMINI_CALL_COOLDOWN = 5.0  # seconds between Gemini calls for same class

# Global rate limiting for Gemini
_gemini_global_last_call: float = 0.0
GEMINI_GLOBAL_MIN_INTERVAL = 4.0  # minimum seconds between ANY Gemini call

_cooldown_lock = threading.Lock()
_cooldowns: dict[str, float] = {}


# ---------------------------------------------------------------------------
# Stage 1 – YOLO
# ---------------------------------------------------------------------------

def load_yolo_model() -> YOLO:
    model = YOLO("yolo11n.pt")
    return model


def detect_targets(frame, model: YOLO) -> list[tuple]:
    """
    Run YOLO on *frame* and return a list of
    (crop, cls_id, x1, y1, x2, y2, yolo_conf) for each target box.
    """
    results = model(frame, conf=YOLO_CONF_THRESHOLD, verbose=False)
    detections = []
    h, w = frame.shape[:2]
    for result in results:
        if result.boxes is None:
            continue
        for box in result.boxes:
            cls_id = int(box.cls[0])
            if cls_id not in TARGET_CLASS_IDS:
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            crop = frame[y1:y2, x1:x2]
            if crop.size > 0:
                detections.append((crop, cls_id, x1, y1, x2, y2, float(box.conf[0])))
    return detections


# ---------------------------------------------------------------------------
# Annotation
# ---------------------------------------------------------------------------

def annotate_frame(frame, detections: list[tuple]) -> bytes:
    """
    Draw bounding boxes on *frame* using the best available label
    (Gemini if ready, otherwise YOLO class name). Returns JPEG bytes.
    """
    out = frame.copy()
    for (_, cls_id, x1, y1, x2, y2, yolo_conf) in detections:
        with _gemini_lock:
            gemini = _gemini_results.get(cls_id)

        if gemini:
            label = f"{gemini['species']} {gemini['confidence']:.0%}"
            color = COLOR_THREAT if gemini["threatening"] else COLOR_SAFE
        else:
            label = f"{COCO_NAMES.get(cls_id, str(cls_id))} {yolo_conf:.0%}"
            color = COLOR_UNCLASSIFIED

        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        cv2.putText(out, label, (x1, max(y1 - 8, 0)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)

    _, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return buf.tobytes()


# ---------------------------------------------------------------------------
# MJPEG stream server
# ---------------------------------------------------------------------------

class _MJPEGHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # suppress per-request logs

    def do_GET(self):
        if self.path != "/stream":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            while True:
                with _frame_lock:
                    data = _latest_annotated
                if data:
                    self.wfile.write(
                        b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n"
                    )
                time.sleep(1 / 30)
        except (BrokenPipeError, ConnectionResetError):
            pass


def start_stream_server(port: int = DEFAULT_STREAM_PORT) -> None:
    server = HTTPServer(("0.0.0.0", port), _MJPEGHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"[Stream] MJPEG feed at http://localhost:{port}/stream")


# ---------------------------------------------------------------------------
# Stage 2 – Gemini (runs in background thread per detection)
# ---------------------------------------------------------------------------

def _bgr_to_pil(crop) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))


def classify_with_gemini(crop, client) -> dict:
    pil_image = _bgr_to_pil(crop)
    buf = BytesIO()
    pil_image.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=[
                GEMINI_PROMPT,
                types.Part.from_bytes(data=buf.read(), mime_type="image/jpeg"),
            ],
        )
        text = response.text.strip()
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            return {
                "species": data.get("species", "unknown"),
                "threatening": bool(data.get("threatening", False)),
                "confidence": float(data.get("confidence", 0.0)),
            }
    except Exception as exc:
        print(f"[Gemini] Error: {exc}")
    return {"threatening": False, "species": "unknown", "confidence": 0.0}


def _gemini_worker(crop, cls_id, gemini_client, ws) -> None:
    """Background thread: classify crop, update label store, send alert if needed."""
    try:
        result = classify_with_gemini(crop, gemini_client)
        result["timestamp"] = datetime.now().strftime("%H:%M:%S")

        with _gemini_lock:
            _gemini_results[cls_id] = result

        species = result["species"]
        threatening = result["threatening"]
        confidence = result["confidence"]

        print(f"[Gemini] species={species}  threatening={threatening}  confidence={confidence:.2f}")
        
        # Log when a target is confirmed with species name
        if species != "unknown" and confidence >= GEMINI_CONF_THRESHOLD:
            print(f"[CONFIRMED] {species.upper()} detected with {confidence:.0%} confidence")

        if not threatening or confidence < GEMINI_CONF_THRESHOLD:
            return

        with _cooldown_lock:
            last = _cooldowns.get(species, 0.0)
            if (time.time() - last) < COOLDOWN_SECONDS:
                print(f"[Cooldown] Skipping {species}")
                return
            _cooldowns[species] = time.time()

        _send_detection(ws, species, confidence, result["timestamp"])
    finally:
        # Mark this class as no longer pending
        with _gemini_lock:
            _gemini_pending.discard(cls_id)


# ---------------------------------------------------------------------------
# WebSocket send
# ---------------------------------------------------------------------------

def _send_detection(ws, species: str, confidence: float, timestamp: str) -> None:
    payload = json.dumps({
        "species": species,
        "threatening": True,
        "confidence": confidence,
        "timestamp": timestamp,
    })
    try:
        ws.send(payload)
        response = ws.recv(timeout=30)
        print(f"[Backend] {response}")
    except Exception as exc:
        print(f"[Backend] WebSocket error: {exc}")


# ---------------------------------------------------------------------------
# Core loop helpers
# ---------------------------------------------------------------------------

def _push_frame(frame, detections: list[tuple]) -> None:
    """Annotate frame and update the MJPEG buffer."""
    jpeg = annotate_frame(frame, detections)
    with _frame_lock:
        global _latest_annotated
        _latest_annotated = jpeg


def _should_call_gemini(cls_id: int) -> bool:
    """Check if we should call Gemini for this class."""
    global _gemini_global_last_call
    
    now = time.time()
    
    with _gemini_lock:
        # Skip if already pending
        if cls_id in _gemini_pending:
            return False
        # Skip if called recently (per-class cooldown)
        last_call = _gemini_last_call.get(cls_id, 0.0)
        if (now - last_call) < GEMINI_CALL_COOLDOWN:
            return False
        # Skip if global rate limit not met
        if (now - _gemini_global_last_call) < GEMINI_GLOBAL_MIN_INTERVAL:
            return False
        return True


def _run_yolo_and_gemini(frame, yolo: YOLO, gemini_client, ws) -> list[tuple]:
    """Run YOLO, kick off Gemini threads for each detection, return detections."""
    global _gemini_global_last_call
    
    detections = detect_targets(frame, yolo)
    if detections:
        print(f"[YOLO] {len(detections)} target(s) found")
    for (crop, cls_id, *_) in detections:
        # Skip if not a known YOLO class
        if cls_id not in COCO_NAMES:
            continue
        
        # Get the YOLO class name
        yolo_class = COCO_NAMES[cls_id]
        
        # Only call Gemini for person, bird, cat, dog, bear (not unknown)
        if yolo_class == "unknown":
            continue
            
        # Only call Gemini if not already pending and not recently called
        if not _should_call_gemini(cls_id):
            continue
        # Mark as pending and record call time
        with _gemini_lock:
            _gemini_pending.add(cls_id)
            _gemini_last_call[cls_id] = time.time()
            _gemini_global_last_call = time.time()
        threading.Thread(
            target=_gemini_worker,
            args=(crop, cls_id, gemini_client, ws),
            daemon=True,
        ).start()
    return detections


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def run_on_image(path: str, yolo: YOLO, gemini_client, ws_url: str) -> None:
    frame = cv2.imread(path)
    if frame is None:
        raise FileNotFoundError(f"Cannot read image: {path}")
    with ws_connect(ws_url) as ws:
        detections = _run_yolo_and_gemini(frame, yolo, gemini_client, ws)
        # For a still image wait for all Gemini threads to finish
        time.sleep(5)
        _push_frame(frame, detections)


def run_on_video(path: str, yolo: YOLO, gemini_client, ws_url: str,
                 stream_port: int = DEFAULT_STREAM_PORT) -> None:
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {path}")
    start_stream_server(stream_port)
    last_detections: list[tuple] = []
    frame_idx = 0
    with ws_connect(ws_url) as ws:
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_idx % SAMPLE_EVERY_N_FRAMES == 0:
                    last_detections = _run_yolo_and_gemini(frame, yolo, gemini_client, ws)
                _push_frame(frame, last_detections)
                frame_idx += 1
        finally:
            cap.release()


def run_on_webcam(camera_index: int, yolo: YOLO, gemini_client, ws_url: str,
                  stream_port: int = DEFAULT_STREAM_PORT) -> None:
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera index {camera_index}")
    start_stream_server(stream_port)
    last_detections: list[tuple] = []
    frame_idx = 0
    print("[Webcam] Press Ctrl+C to stop.")
    with ws_connect(ws_url) as ws:
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("[Webcam] Failed to grab frame.")
                    break
                if frame_idx % SAMPLE_EVERY_N_FRAMES == 0:
                    last_detections = _run_yolo_and_gemini(frame, yolo, gemini_client, ws)
                _push_frame(frame, last_detections)
                frame_idx += 1
        except KeyboardInterrupt:
            print("[Webcam] Stopped by user.")
        finally:
            cap.release()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="FarmGuardian predator detection")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--input", metavar="FILE", help="Path to image or video file")
    group.add_argument("--camera", metavar="INDEX", type=int, default=None,
                       help="Webcam index (default 0 if --input not given)")
    parser.add_argument("--api", default=DEFAULT_WS_URL,
                        help=f"Backend WebSocket URL (default: {DEFAULT_WS_URL})")
    parser.add_argument("--stream-port", type=int, default=DEFAULT_STREAM_PORT,
                        help=f"MJPEG stream port (default: {DEFAULT_STREAM_PORT})")
    parser.add_argument("--confidence", type=float, default=GEMINI_CONF_THRESHOLD,
                        help=f"Gemini confidence threshold (default: {GEMINI_CONF_THRESHOLD})")
    args = parser.parse_args()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY is not set. Add it to your .env file.")

    gemini_client = genai.Client(api_key=api_key)

    print("[Init] Loading YOLO11n…")
    yolo = load_yolo_model()
    print("[Init] Ready.")

    if args.input:
        ext = os.path.splitext(args.input)[1].lower()
        if ext in {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff"}:
            run_on_image(args.input, yolo, gemini_client, args.api)
        else:
            run_on_video(args.input, yolo, gemini_client, args.api, args.stream_port)
    else:
        cam_idx = args.camera if args.camera is not None else 0
        run_on_webcam(cam_idx, yolo, gemini_client, args.api, args.stream_port)


if __name__ == "__main__":
    main()
