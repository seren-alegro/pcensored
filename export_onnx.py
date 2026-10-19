#!/usr/bin/env python3
"""Convert ultralytics .pt model to ONNX (read-only on the source file).

Usage:
    python export_onnx.py <input.pt> <output.onnx> [imgsz]

The source .pt is only read; the .onnx is written to the destination path
(which should be OUTSIDE the original models/ folder).
"""
import sys
from pathlib import Path

from ultralytics import YOLO


def main() -> None:
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".onnx")
    imgsz = int(sys.argv[3]) if len(sys.argv) > 3 else 640

    print(f"[EXPORT] Loading {src} (read-only)")
    model = YOLO(str(src))
    print(f"[EXPORT] Exporting to {dst} (imgsz={imgsz}, opset=12)")
    model.export(format="onnx", imgsz=imgsz, opset=12, simplify=True)
    # ultralytics writes <src-stem>.onnx next to the source; move it
    produced = src.with_suffix(".onnx")
    if produced != dst:
        dst.parent.mkdir(parents=True, exist_ok=True)
        produced.replace(dst)
    print(f"[EXPORT] Done: {dst}")


if __name__ == "__main__":
    main()
