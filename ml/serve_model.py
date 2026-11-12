"""AI model service: runs the SAME int8 TFLite model the ESP32 will run, so it can be tested on the web
before buying the hardware. The Django dashboard ("Test the AI" page) talks to it.

    ml\\.venv\\Scripts\\python ml\\serve_model.py            (started automatically by RUN_DEMO.bat)

    GET  http://127.0.0.1:8500/health     -> model information
    POST http://127.0.0.1:8500/classify   body = image bytes (JPEG/PNG) -> scores for each class

Pre-processing is the same as on the camera: centre-crop to a square, resize to the model size,
raw pixels 0..255 (the scaling to -1..1 is inside the model), int8 quantisation.
"""

import io
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
import numpy as np  # noqa: E402
import tensorflow as tf  # noqa: E402
from PIL import Image, ImageOps  # noqa: E402

OUT = Path(__file__).resolve().parent / "output"
HOST, PORT = os.getenv("AI_HOST", "127.0.0.1"), int(os.getenv("AI_PORT", "8500"))
MAX_BYTES = 8 * 1024 * 1024


class Model:
    def __init__(self, folder=OUT):
        self.path = folder / "model_int8.tflite"
        self.labels = (folder / "labels.txt").read_text(encoding="utf8").split()
        self.metrics = json.loads((folder / "metrics.json").read_text(encoding="utf8"))
        self.interp = tf.lite.Interpreter(model_path=str(self.path), num_threads=2)
        self.interp.allocate_tensors()
        self.inp = self.interp.get_input_details()[0]
        self.out = self.interp.get_output_details()[0]
        self.size = int(self.inp["shape"][1])
        self.lock = threading.Lock()  # the interpreter is not thread-safe

    def info(self):
        m = self.metrics
        return {
            "model": m.get("model"), "input": f"{self.size}x{self.size} RGB", "labels": self.labels,
            "file": self.path.name, "size_kb": round(self.path.stat().st_size / 1024),
            "test_accuracy": m.get("int8", {}).get("accuracy"),
            "test_compartment_accuracy": m.get("int8", {}).get("compartment_accuracy"),
            "test_images": m.get("test_images"), "trained_images": m.get("training_images"),
        }

    def preprocess(self, data):
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        img = ImageOps.fit(img, (self.size, self.size), Image.BILINEAR, centering=(0.5, 0.5))  # like the camera
        x = np.asarray(img, dtype=np.float32)[None]
        scale, zero = self.inp["quantization"]
        return np.clip(np.round(x / scale + zero), -128, 127).astype(np.int8)

    def classify(self, data):
        x = self.preprocess(data)
        with self.lock:
            self.interp.set_tensor(self.inp["index"], x)
            t0 = time.perf_counter()
            self.interp.invoke()
            ms = (time.perf_counter() - t0) * 1000
            raw = self.interp.get_tensor(self.out["index"])[0].astype(np.float32)
        scale, zero = self.out["quantization"]
        probs = (raw - zero) * scale  # de-quantise (softmax output 0..1)
        probs = probs / max(float(probs.sum()), 1e-6)
        scores = {label: round(float(p), 4) for label, p in zip(self.labels, probs)}
        best = max(scores, key=scores.get)
        return {"label": best, "confidence": scores[best], "scores": scores, "inference_ms": round(ms, 2)}


def make_handler(model):
    class Handler(BaseHTTPRequestHandler):
        def send_json(self, code, payload):
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.rstrip("/") == "/health":
                return self.send_json(200, {"ok": True, **model.info()})
            self.send_json(404, {"detail": "Not found"})

        def do_POST(self):
            if self.path.rstrip("/") != "/classify":
                return self.send_json(404, {"detail": "Not found"})
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 < length <= MAX_BYTES:
                return self.send_json(400, {"detail": "Send one image (max 8 MB)."})
            try:
                self.send_json(200, model.classify(self.rfile.read(length)))
            except Exception as exc:  # not an image, corrupt file...
                self.send_json(400, {"detail": f"Could not read the image: {exc}"})

        def log_message(self, fmt, *args):  # quiet console: one line per classification
            if "POST" in (args[0] if args else ""):
                print(f"[AI] {self.address_string()} {fmt % args}")

    return Handler


def main():
    model = Model()
    print(f"AI model service: {model.info()['model']}, input {model.size}x{model.size}, labels {model.labels}")
    print(f"Listening on http://{HOST}:{PORT}  (keep this window open; the dashboard's 'Test the AI' page uses it)")
    ThreadingHTTPServer((HOST, PORT), make_handler(model)).serve_forever()


if __name__ == "__main__":
    main()
