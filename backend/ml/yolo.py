"""
FarmGuardian – two-stage predator detection pipeline
Stage 1: YOLOv8n  →  locate animals in frame (fast, CPU-friendly)
Stage 2: Gemini Vision  →  classify ROI and decide if threatening
"""

import argparse
import json
import os
import re
import time
from io import BytesIO

import cv2
from google import genai
from google.genai import types
import requests
from dotenv import load_dotenv
from PIL import Image
from ultralytics import YOLO

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# COCO class IDs that are animals
ANIMAL_CLASS_IDS = {14, 15, 16, 17, 18, 19, 20, 21, 22, 23}
# 14=bird, 15=cat, 16=dog, 17=horse, 18=sheep, 19=cow,
# 20=elephant, 21=bear, 22=zebra, 23=giraffe

YOLO_CONF_THRESHOLD = 0.3   # low — Gemini does real classification
GEMINI_CONF_THRESHOLD = 0.6  # min confidence to trigger alert
COOLDOWN_SECONDS = 15
SAMPLE_EVERY_N_FRAMES = 15   # ~2 fps at 30 fps capture

GEMINI_PROMPT = (
    "What animal is this? If it is a predatory or farm-threatening animal "
    "(e.g., dog, coyote, wolf, fox, bear, hawk, eagle, raccoon, crow, rat, deer, wild boar), "
    'respond with JSON: {"species": "<name>", "threatening": true/false, "confidence": 0.0-1.0}. '
    'If you cannot identify it or it\'s not an animal, return {"threatening": false}.'
)

# may need to change in the future
DEFAULT_API_URL = "http://localhost:8000/detection"


# ---------------------------------------------------------------------------
# Stage 1 – YOLO
# ---------------------------------------------------------------------------

def load_yolo_model() -> YOLO:
    """Load YOLOv8n (auto-downloaded on first run, ~6 MB)."""
    model = YOLO("yolo11n.pt")
    return model


def detect_animals(frame, model: YOLO) -> list:
    """
    Run YOLOv8n on *frame* (BGR ndarray) and return a list of cropped BGR
    images, one per animal bounding box found above YOLO_CONF_THRESHOLD.
    """
    results = model(frame, conf=YOLO_CONF_THRESHOLD, verbose=False)
    crops = []
    for result in results:
        boxes = result.boxes
        if boxes is None:
            continue
        for box in boxes:
            cls_id = int(box.cls[0])
            if cls_id not in ANIMAL_CLASS_IDS:
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            # Clamp to frame bounds
            h, w = frame.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            crop = frame[y1:y2, x1:x2]
            if crop.size > 0:
                crops.append(crop)
    return crops


# ---------------------------------------------------------------------------
# Stage 2 – Gemini
# ---------------------------------------------------------------------------

def _bgr_crop_to_pil(crop) -> Image.Image:
    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def classify_with_gemini(crop, client) -> dict:
    """
    Send *crop* (BGR ndarray) to Gemini Vision.
    Returns a dict with keys: species, threatening, confidence.
    On error returns {"threatening": False}.
    """
    pil_image = _bgr_crop_to_pil(crop)

    # Encode as JPEG in-memory
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

        # Extract JSON from the response (model may wrap it in markdown)
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


# ---------------------------------------------------------------------------
# Cooldown helpers
# ---------------------------------------------------------------------------

def _is_on_cooldown(species: str, cooldowns: dict) -> bool:
    last = cooldowns.get(species, 0.0)
    return (time.time() - last) < COOLDOWN_SECONDS


def _update_cooldown(species: str, cooldowns: dict) -> None:
    cooldowns[species] = time.time()


# ---------------------------------------------------------------------------
# Core frame processor
# ---------------------------------------------------------------------------

def process_frame(frame, yolo: YOLO, gemini_client, api_url: str, cooldowns: dict) -> None:
    """
    Full pipeline for a single frame:
    1. YOLO animal detection
    2. Gemini classification on each crop
    3. POST to backend if threatening and not on cooldown
    """
    crops = detect_animals(frame, yolo)
    if not crops:
        return

    print(f"[YOLO] {len(crops)} animal region(s) found — classifying with Gemini…")

    for crop in crops:
        result = classify_with_gemini(crop, gemini_client)
        species = result.get("species", "unknown")
        threatening = result.get("threatening", False)
        confidence = result.get("confidence", 0.0)

        print(f"[Gemini] species={species}  threatening={threatening}  confidence={confidence:.2f}")

        if not threatening or confidence < GEMINI_CONF_THRESHOLD:
            continue

        if _is_on_cooldown(species, cooldowns):
            print(f"[Cooldown] Skipping {species} (cooldown active)")
            continue

        _update_cooldown(species, cooldowns)
        _post_detection(species, confidence, api_url)


def _post_detection(species: str, confidence: float, api_url: str) -> None:
    payload = {"species": species, "confidence": confidence}
    try:
        resp = requests.post(api_url, json=payload, timeout=5)
        print(f"[Backend] POST {api_url} → {resp.status_code} {resp.text}")
    except requests.RequestException as exc:
        print(f"[Backend] Failed to reach {api_url}: {exc}")


# ---------------------------------------------------------------------------
# Entry points: image / video / webcam
# ---------------------------------------------------------------------------

def run_on_image(path: str, yolo: YOLO, gemini_client, api_url: str) -> None:
    frame = cv2.imread(path)
    if frame is None:
        raise FileNotFoundError(f"Cannot read image: {path}")
    cooldowns: dict = {}
    process_frame(frame, yolo, gemini_client, api_url, cooldowns)


def run_on_video(path: str, yolo: YOLO, gemini_client, api_url: str) -> None:
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {path}")
    cooldowns: dict = {}
    frame_idx = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % SAMPLE_EVERY_N_FRAMES == 0:
                process_frame(frame, yolo, gemini_client, api_url, cooldowns)
            frame_idx += 1
    finally:
        cap.release()


def run_on_webcam(camera_index: int, yolo: YOLO, gemini_client, api_url: str) -> None:
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera index {camera_index}")
    cooldowns: dict = {}
    frame_idx = 0
    print("[Webcam] Press Ctrl+C to stop.")
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[Webcam] Failed to grab frame.")
                break
            if frame_idx % SAMPLE_EVERY_N_FRAMES == 0:
                process_frame(frame, yolo, gemini_client, api_url, cooldowns)
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
    parser.add_argument("--api", default=DEFAULT_API_URL,
                        help=f"Backend detection endpoint (default: {DEFAULT_API_URL})")
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
        # Auto-detect image vs video by extension
        ext = os.path.splitext(args.input)[1].lower()
        if ext in {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff"}:
            run_on_image(args.input, yolo, gemini_client, args.api)
        else:
            run_on_video(args.input, yolo, gemini_client, args.api)
    else:
        cam_idx = args.camera if args.camera is not None else 0
        run_on_webcam(cam_idx, yolo, gemini_client, args.api)


if __name__ == "__main__":
    main()
