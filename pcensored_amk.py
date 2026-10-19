#!/usr/bin/env python3
"""
pcensored-amk: alpha-mask-killer + PCensored 합친 파이썬 도구.

파이프라인 (이미지 1장당):
  1. 알파 합성: 투명 채널이 있으면 지정 배경색 위에 합성 (alpha-mask-killer)
  2. NTD11 탐지: 전체 스캔 + 스마트 크롭 4회 (PCensored)
  3. 모자이크: 탐지 영역에 모자이크
  4. WEBP 저장

필요: pip install ultralytics numpy Pillow
모델: ntd11.pt (Civitai에서 내려받은 .pt를 그대로 사용, 변환 불필요)

사용법:
  python3 pcensored_amk.py 입력폴더 -o 출력폴더
  python3 pcensored_amk.py 이미지.png -o 출력폴더 --confidence 0.3
"""

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

try:
    from ultralytics import YOLO
except ImportError:
    sys.exit("ultralytics가 없어요: pip install ultralytics")

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

INPUT_SIZE = 1280

SMART_CROPS = [
    (0.15, 0.20, 0.85, 0.95),  # CENTER
    (0.00, 0.40, 1.00, 1.00),  # LOWER
    (0.00, 0.25, 0.65, 1.00),  # LEFT
    (0.35, 0.25, 1.00, 1.00),  # RIGHT
]
CROP_SCALE = 2.0
NMS_IOU = 0.45
MERGE_IOU = 0.4
MIN_MOSAIC = 32

IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


# ---------------------------------------------------------------------------
# 1. 알파 합성 (alpha-mask-killer)
# ---------------------------------------------------------------------------

def flatten_alpha(img: Image.Image, bg: tuple) -> Image.Image:
    """투명 채널이 있으면 배경색 위에 합성, 없으면 RGB 변환."""
    if img.mode in ("RGBA", "LA"):
        bg_img = Image.new("RGB", img.size, bg)
        bg_img.paste(img, mask=img.split()[-1])
        return bg_img
    if img.mode == "P":
        # 팔레트 투명도 처리
        if "transparency" in img.info:
            img = img.convert("RGBA")
            bg_img = Image.new("RGB", img.size, bg)
            bg_img.paste(img, mask=img.split()[-1])
            return bg_img
        return img.convert("RGB")
    return img.convert("RGB")


# ---------------------------------------------------------------------------
# 2. NTD11 탐지 (Rust detector.rs 포트)
# ---------------------------------------------------------------------------

def _allowed(label: str) -> bool:
    # pixiv 기준: 유두(nipples)는 검열하지 않음
    label = label.lower()
    if "pussy" in label or "vagina" in label:
        return True
    if "penis" in label or "testicle" in label:
        return True
    if "anus" in label:
        return True
    return False


def _iou(a, b) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    aa = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    ab = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    return inter / (aa + ab - inter + 1e-6)




class Ntd11Detector:
    def __init__(self, pt_path: str, threads: int = 4):
        try:
            import torch
            torch.set_num_threads(max(1, threads))
        except Exception:
            pass
        self.model = YOLO(pt_path)
        self.names = self.model.names  # {idx: label}

    def detect_raw(self, rgb: np.ndarray, confidence: float):
        """단일 이미지 추론. 좌표는 입력 이미지 기준 픽셀."""
        h, w = rgb.shape[:2]
        results = self.model.predict(rgb, conf=confidence, iou=NMS_IOU,
                                     imgsz=INPUT_SIZE, verbose=False)
        dets = []
        boxes = results[0].boxes
        if boxes is None:
            return dets
        for xyxy, conf, cls in zip(boxes.xyxy, boxes.conf, boxes.cls):
            x1, y1, x2, y2 = (float(v) for v in xyxy.tolist())
            dets.append({
                "label": str(self.names[int(cls)]),
                "score": float(conf),
                "x1": int(max(0.0, min(w, x1))),
                "y1": int(max(0.0, min(h, y1))),
                "x2": int(max(0.0, min(w, x2))),
                "y2": int(max(0.0, min(h, y2))),
            })
        return dets

    def _detect_ntd11(self, rgb, ox, oy, scale, confidence):
        raw = self.detect_raw(rgb, confidence)
        out = []
        for d in raw:
            if not _allowed(d["label"]):
                continue
            out.append({
                "label": d["label"],
                "score": d["score"],
                "x1": int(d["x1"] / scale) + ox,
                "y1": int(d["y1"] / scale) + oy,
                "x2": int(d["x2"] / scale) + ox,
                "y2": int(d["y2"] / scale) + oy,
            })
        return out

    @staticmethod
    def _merge_duplicates(dets):
        final = []
        for d in dets:
            dup = None
            for i, e in enumerate(final):
                if d["label"] != e["label"]:
                    continue
                a = (d["x1"], d["y1"], d["x2"], d["y2"])
                b = (e["x1"], e["y1"], e["x2"], e["y2"])
                if _iou(a, b) >= MERGE_IOU:
                    dup = i
                    break
            if dup is None:
                final.append(d)
            elif d["score"] > final[dup]["score"]:
                final[dup] = d
        return final

    def detect(self, rgb: np.ndarray, confidence: float,
               smart_crop: bool = True):
        """full scan + smart crops → merge (원본 detect와 동일)."""
        h, w = rgb.shape[:2]
        dets = self._detect_ntd11(rgb, 0, 0, 1.0, confidence)
        if smart_crop:
            pil = Image.fromarray(rgb)
            for fx1, fy1, fx2, fy2 in SMART_CROPS:
                x1, y1 = int(w * fx1), int(h * fy1)
                x2, y2 = int(w * fx2), int(h * fy2)
                cw, ch = x2 - x1, y2 - y1
                if cw < 10 or ch < 10:
                    continue
                crop = pil.crop((x1, y1, x2, y2))
                big = crop.resize((int(cw * CROP_SCALE), int(ch * CROP_SCALE)),
                                  Image.LANCZOS)
                dets += self._detect_ntd11(np.array(big), x1, y1,
                                           CROP_SCALE, confidence)
        return self._merge_duplicates(dets)


# ---------------------------------------------------------------------------
# 3. 모자이크 (Rust mosaic.rs 포트)
# ---------------------------------------------------------------------------

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def censor_image(img: Image.Image, dets, block_size=20, padding=15):
    """탐지 영역에 모자이크. img는 RGB PIL 이미지 (in place 아님, 복사 반환)."""
    img = img.copy()
    w, h = img.size
    for d in dets:
        x1 = _clamp(d["x1"] - padding, 0, w)
        y1 = _clamp(d["y1"] - padding, 0, h)
        x2 = _clamp(d["x2"] + padding, 0, w)
        y2 = _clamp(d["y2"] + padding, 0, h)
        if x2 - x1 < MIN_MOSAIC:
            c = (x1 + x2) // 2
            x1 = _clamp(c - MIN_MOSAIC // 2, 0, w)
            x2 = _clamp(c + MIN_MOSAIC // 2, 0, w)
        if y2 - y1 < MIN_MOSAIC:
            c = (y1 + y2) // 2
            y1 = _clamp(c - MIN_MOSAIC // 2, 0, h)
            y2 = _clamp(c + MIN_MOSAIC // 2, 0, h)
        rw, rh = x2 - x1, y2 - y1
        if rw <= 1 or rh <= 1:
            continue
        region = img.crop((x1, y1, x2, y2))
        small = region.resize((max(rw // block_size, 1), max(rh // block_size, 1)),
                              Image.NEAREST)
        mosaic = small.resize((rw, rh), Image.NEAREST)
        img.paste(mosaic, (x1, y1))
    return img


# ---------------------------------------------------------------------------
# 4. CLI
# ---------------------------------------------------------------------------

def parse_bg(s: str) -> tuple:
    s = s.lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def collect_images(path: Path):
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*")
                  if p.is_file() and p.suffix.lower() in IMG_EXTS)


def main():
    ap = argparse.ArgumentParser(
        description="alpha-mask-killer + PCensored 합친 파이썬 도구")
    ap.add_argument("input", help="이미지 파일 또는 폴더")
    ap.add_argument("-o", "--output", default="output",
                    help="출력 폴더 (기본: output)")
    ap.add_argument("--model", default=None,
                    help=".pt 모델 경로 (기본: 스크립트 옆 ntd11.pt)")
    ap.add_argument("--confidence", type=float, default=0.10)
    ap.add_argument("--block", type=int, default=20, help="모자이크 강도")
    ap.add_argument("--padding", type=int, default=15)
    ap.add_argument("--quality", type=int, default=95, help="WEBP 품질")
    ap.add_argument("--bg", default="ffffff",
                    help="알파 합성 배경색 hex (기본: ffffff)")
    ap.add_argument("--no-smart-crop", action="store_true",
                    help="스마트 크롭 끄기 (빠름)")
    ap.add_argument("--threads", type=int, default=4,
                    help="CPU 스레드 수")
    args = ap.parse_args()

    script_dir = Path(__file__).resolve().parent
    model = args.model or str(script_dir / "ntd11.pt")
    if not os.path.isfile(model):
        sys.exit(f"모델이 없어요: {model}\n"
                 f"Civitai에서 .pt 모델을 내려받아 ntd11.pt로 두거나\n"
                 f"--model 로 경로를 지정하세요.")

    bg = parse_bg(args.bg)
    in_path = Path(args.input)
    if not in_path.exists():
        sys.exit(f"입력 경로가 없어요: {in_path}")
    files = collect_images(in_path)
    if not files:
        sys.exit("이미지 파일이 없어요.")

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"모델 로딩 중… ({model})")
    det = Ntd11Detector(model, threads=args.threads)

    total = len(files)
    t0 = time.time()
    for i, f in enumerate(files, 1):
        t1 = time.time()
        try:
            img = Image.open(f)
        except Exception as e:
            print(f"[{i}/{total}] {f.name}: 열기 실패 ({e})")
            continue
        # 1. 알파 합성
        flat = flatten_alpha(img, bg)
        rgb = np.array(flat)
        # 2. 탐지
        dets = det.detect(rgb, args.confidence,
                          smart_crop=not args.no_smart_crop)
        # 3. 모자이크
        out_img = censor_image(flat, dets, args.block, args.padding)
        # 4. 저장
        out_path = out_dir / (f.stem + "_censored.webp")
        out_img.save(out_path, "WEBP", quality=args.quality)
        dt = time.time() - t1
        tag = f"{len(dets)}개 영역" if dets else "탐지 없음"
        print(f"[{i}/{total}] {f.name} → {out_path.name} ({tag}, {dt:.1f}s)")
    print(f"완료: {total}장, {time.time() - t0:.1f}s → {out_dir}")


if __name__ == "__main__":
    main()
