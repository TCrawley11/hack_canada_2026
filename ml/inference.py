from ultralytics import YOLO
import matplotlib.pyplot as plt
import numpy as np

def export_onnx(model):
    return  model.export(format="onnx")

def main():
    model = YOLO("yolo26n.pt")
    results = model("test_images/rat_test1.jpg")
    results[0].show()

if __name__ == "__main__":
    main()

