import argparse
import numpy as np
import cv2
import supervision as sv
from pathlib import Path
from PytorchWildlife.models import detection as pw_detection
from PytorchWildlife.models import classification as pw_classification

OUT_DIR = Path(__file__).parent / "inf_tests"



def annotate_detections(img_rgb: np.ndarray, detection_result: dict, classification_result: dict) -> np.ndarray:
    detections = detection_result.get("detections")
    if detections is None or len(detections) == 0:
        return img_rgb

    label = classification_result.get("prediction", "")
    confidence = classification_result.get("confidence", 0.0)
    labels = [f"{label} ({confidence:.0%})"] * len(detections)

    box_annotator = sv.BoxAnnotator(thickness=4)
    label_annotator = sv.LabelAnnotator(
        text_color=sv.Color.BLACK, text_thickness=2, text_scale=1.0
    )
    img = box_annotator.annotate(scene=img_rgb.copy(), detections=detections)
    img = label_annotator.annotate(scene=img, detections=detections, labels=labels)
    return img


def run_on_image(img_path: Path, detection_model, classification_model):
    img = cv2.imread(str(img_path))
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    detection_result = detection_model.single_image_detection(img_rgb)
    classification_result = classification_model.single_image_classification(img_rgb)

    label = classification_result.get("prediction", "")
    confidence = classification_result.get("confidence", 0.0)
    print(f"[{img_path.name}] Detection: {detection_result}")
    print(f"[{img_path.name}] Classification: {label} ({confidence:.0%})")

    annotated = annotate_detections(img_rgb, detection_result, classification_result)

    out_path = OUT_DIR / img_path.name
    cv2.imwrite(str(out_path), cv2.cvtColor(annotated, cv2.COLOR_RGB2BGR))
    print(f"Saved to {out_path}")


def run_on_video(video_path: Path, detection_model, classification_model):
    cap = cv2.VideoCapture(str(video_path))
    frame_idx = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        detection_result = detection_model.single_image_detection(img_rgb)
        classification_result = classification_model.single_image_classification(img_rgb)

        label = classification_result.get("prediction", "")
        confidence = classification_result.get("confidence", 0.0)
        print(f"Frame {frame_idx} | {label} ({confidence:.0%}) | Detection: {detection_result}")
        frame_idx += 1

    cap.release()


def main():
    parser = argparse.ArgumentParser(description="Wildlife detection and classification inference")
    parser.add_argument("input", type=Path, help="Path to an image or video file")
    args = parser.parse_args()

    input_path: Path = args.input
    if not input_path.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")

    OUT_DIR.mkdir(exist_ok=True)

    detection_model = pw_detection.MegaDetectorV6(version="MDV6-yolov9-c")
    classification_model = pw_classification.DFNE()

    video_exts = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    if input_path.suffix.lower() in video_exts:
        run_on_video(input_path, detection_model, classification_model)
    else:
        run_on_image(input_path, detection_model, classification_model)


if __name__ == "__main__":
    main()
