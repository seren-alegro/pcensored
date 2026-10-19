#!/usr/bin/env python3
"""
pcensored-amk GUI (tkinter).

실행: uv run pcensored_amk_gui.py
"""

import os
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, scrolledtext, ttk

import numpy as np
from PIL import Image

import pcensored_amk as core


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PCensored + AlphaMaskKiller")
        self.geometry("640x720")

        self.files = []
        self.out_dir = str(Path.cwd() / "output")
        self.stop_event = threading.Event()
        self.log_q = queue.Queue()
        self.worker = None

        self._build_ui()
        self.after(100, self._poll_log)

    # -- UI ---------------------------------------------------------------
    def _build_ui(self):
        pad = {"padx": 10, "pady": 4}
        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, **pad)

        # 입력
        ttk.Label(frm, text="입력", font=("", 11, "bold")).pack(anchor="w")
        row = ttk.Frame(frm)
        row.pack(fill="x")
        ttk.Button(row, text="파일 선택", command=self.pick_files).pack(side="left")
        ttk.Button(row, text="폴더 선택", command=self.pick_folder).pack(side="left", padx=5)
        self.in_label = ttk.Label(row, text="선택된 이미지: 0장")
        self.in_label.pack(side="left", padx=10)

        # 출력
        ttk.Label(frm, text="출력 폴더", font=("", 11, "bold")).pack(anchor="w", pady=(8, 0))
        row2 = ttk.Frame(frm)
        row2.pack(fill="x")
        self.out_var = tk.StringVar(value=self.out_dir)
        ttk.Entry(row2, textvariable=self.out_var, width=50).pack(side="left", fill="x", expand=True)
        ttk.Button(row2, text="변경", command=self.pick_out).pack(side="left", padx=5)

        # 옵션
        ttk.Label(frm, text="옵션", font=("", 11, "bold")).pack(anchor="w", pady=(8, 0))
        opt = ttk.Frame(frm)
        opt.pack(fill="x")
        self.conf_var = self._slider(opt, "Confidence", 0.05, 0.90, 0.10, 0)
        self.block_var = self._slider(opt, "모자이크 강도", 4, 64, 20, 1)
        self.pad_var = self._slider(opt, "Padding", 0, 64, 15, 2)
        self.q_var = self._slider(opt, "WEBP 품질", 10, 100, 95, 3)

        row3 = ttk.Frame(frm)
        row3.pack(fill="x", pady=4)
        ttk.Label(row3, text="배경색(hex):").pack(side="left")
        self.bg_var = tk.StringVar(value="ffffff")
        ttk.Entry(row3, textvariable=self.bg_var, width=10).pack(side="left", padx=5)
        self.crop_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row3, text="스마트 크롭", variable=self.crop_var).pack(side="left", padx=10)
        ttk.Label(row3, text="스레드:").pack(side="left")
        self.thread_var = tk.StringVar(value="4")
        ttk.Entry(row3, textvariable=self.thread_var, width=6).pack(side="left", padx=5)

        # 실행 버튼
        row4 = ttk.Frame(frm)
        row4.pack(fill="x", pady=8)
        self.run_btn = ttk.Button(row4, text="실행", command=self.start)
        self.run_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.stop_btn = ttk.Button(row4, text="중지", command=self.request_stop, state="disabled")
        self.stop_btn.pack(side="left", fill="x", expand=True, padx=(5, 0))

        # 진행
        self.prog_var = tk.StringVar(value="대기 중")
        ttk.Label(frm, textvariable=self.prog_var).pack(anchor="w")
        self.prog = ttk.Progressbar(frm, mode="determinate")
        self.prog.pack(fill="x")

        # 로그
        ttk.Label(frm, text="로그", font=("", 11, "bold")).pack(anchor="w", pady=(8, 0))
        self.log = scrolledtext.ScrolledText(frm, height=14, state="disabled")
        self.log.pack(fill="both", expand=True)

    def _slider(self, parent, label, lo, hi, init, row):
        f = ttk.Frame(parent)
        f.pack(fill="x", pady=2)
        ttk.Label(f, text=label, width=12).pack(side="left")
        var = tk.DoubleVar(value=init)
        val = ttk.Label(f, text=str(init), width=6)
        val.pack(side="right")
        s = ttk.Scale(f, from_=lo, to=hi, variable=var,
                      command=lambda v: val.config(text=f"{float(v):.2f}" if hi <= 1 else f"{float(v):.0f}"))
        s.pack(side="left", fill="x", expand=True, padx=5)
        return var

    # -- 파일 선택 ---------------------------------------------------------
    def pick_files(self):
        paths = filedialog.askopenfilenames(
            title="이미지 선택",
            filetypes=[("이미지", "*.png *.jpg *.jpeg *.webp *.bmp"), ("모든 파일", "*.*")])
        if paths:
            self.files = [Path(p) for p in paths]
            self.in_label.config(text=f"선택된 이미지: {len(self.files)}장")

    def pick_folder(self):
        d = filedialog.askdirectory(title="이미지 폴더 선택")
        if d:
            self.files = core.collect_images(Path(d))
            self.in_label.config(text=f"선택된 이미지: {len(self.files)}장")

    def pick_out(self):
        d = filedialog.askdirectory(title="출력 폴더 선택")
        if d:
            self.out_var.set(d)

    # -- 실행 --------------------------------------------------------------
    def start(self):
        if not self.files:
            self._log("이미지를 먼저 선택하세요.")
            return
        if self.worker and self.worker.is_alive():
            return
        try:
            threads = max(1, int(self.thread_var.get()))
        except ValueError:
            threads = 4
        opts = {
            "confidence": float(self.conf_var.get()),
            "block": int(float(self.block_var.get())),
            "padding": int(float(self.pad_var.get())),
            "quality": int(float(self.q_var.get())),
            "bg": core.parse_bg(self.bg_var.get().strip() or "ffffff"),
            "smart_crop": self.crop_var.get(),
            "threads": threads,
            "out_dir": Path(self.out_var.get()),
        }
        self.stop_event.clear()
        self.run_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.prog["maximum"] = len(self.files)
        self.prog["value"] = 0
        self.worker = threading.Thread(target=self._work,
                                       args=(list(self.files), opts),
                                       daemon=True)
        self.worker.start()

    def request_stop(self):
        self.stop_event.set()
        self._log("중지 요청됨…")

    def _work(self, files, opts):
        model = str(Path(__file__).resolve().parent / "ntd11.pt")
        if not os.path.isfile(model):
            self.log_q.put(("log", f"모델이 없어요: {model}"))
            self.log_q.put(("done", None))
            return
        out_dir = opts["out_dir"]
        out_dir.mkdir(parents=True, exist_ok=True)
        self.log_q.put(("log", f"모델 로딩 중… ({Path(model).name})"))
        try:
            det = core.Ntd11Detector(model, threads=opts["threads"])
        except Exception as e:
            self.log_q.put(("log", f"모델 로드 실패: {e}"))
            self.log_q.put(("done", None))
            return
        total = len(files)
        t0 = time.time()
        for i, f in enumerate(files, 1):
            if self.stop_event.is_set():
                self.log_q.put(("log", "중지됨"))
                break
            t1 = time.time()
            try:
                img = Image.open(f)
            except Exception as e:
                self.log_q.put(("log", f"[{i}/{total}] {f.name}: 열기 실패 ({e})"))
                self.log_q.put(("progress", i))
                continue
            flat = core.flatten_alpha(img, opts["bg"])
            rgb = np.array(flat)
            dets = det.detect(rgb, opts["confidence"], smart_crop=opts["smart_crop"])
            out_img = core.censor_image(flat, dets, opts["block"], opts["padding"])
            out_path = out_dir / (f.stem + "_censored.webp")
            out_img.save(out_path, "WEBP", quality=opts["quality"])
            dt = time.time() - t1
            tag = f"{len(dets)}개 영역" if dets else "탐지 없음"
            self.log_q.put(("log", f"[{i}/{total}] {f.name} → {out_path.name} ({tag}, {dt:.1f}s)"))
            self.log_q.put(("progress", i))
        self.log_q.put(("log", f"완료: {total}장, {time.time() - t0:.1f}s → {out_dir}"))
        self.log_q.put(("done", None))

    def _poll_log(self):
        try:
            while True:
                kind, msg = self.log_q.get_nowait()
                if kind == "log":
                    self._log(msg)
                elif kind == "progress":
                    self.prog["value"] = msg
                    self.prog_var.set(f"{msg}/{len(self.files)} 처리 중…")
                elif kind == "done":
                    self.run_btn.config(state="normal")
                    self.stop_btn.config(state="disabled")
                    self.prog_var.set("완료")
        except queue.Empty:
            pass
        self.after(100, self._poll_log)

    def _log(self, msg):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.config(state="disabled")


if __name__ == "__main__":
    App().mainloop()
