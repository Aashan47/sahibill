"""SAM 3 (Meta, Segment Anything with Concepts) on Modal: find the meter-reading photo printed on a bill.

The bill prints a small, half-toned photo of the meter with its date and time stamp. Read from the whole
bill photo, the reader often cannot make it out. SAM 3 is prompted with a short text concept ("electricity
meter") and returns boxes; the box is cropped in code and read again at full resolution.

SAM 3 rather than SAM 3.1: the 3.1 release is a checkpoint for Meta's own sam3 package, aimed at video
tracking, with no Transformers integration; SAM 3 has one (transformers 5.0.0, `Sam3Model`).
  modal run sahibill/vision/modal_sam.py::boxes --photos <dir> --out <file.json>
"""
from __future__ import annotations

import modal

app = modal.App("sahibill-sam")
cache = modal.Volume.from_name("sahibill-sam-weights", create_if_missing=True)
image = (modal.Image.debian_slim(python_version="3.11")
         .pip_install("torch==2.8.0", "torchvision==0.23.0", "transformers==5.0.0", "accelerate", "pillow")
         .env({"HF_HOME": "/cache/hf"}))
PROMPTS = ("electricity meter", "digital meter display")


@app.cls(image=image, gpu=["L4", "A10G"], volumes={"/cache": cache}, secrets=[modal.Secret.from_name("huggingface")],
         timeout=900, scaledown_window=60)
class Sam:
    @modal.enter()
    def load(self):
        import os
        import torch
        from transformers import Sam3Model, Sam3Processor
        token = os.environ.get("HF_TOKEN") or os.environ.get("HF_TOKEN_META") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        self.model = Sam3Model.from_pretrained("facebook/sam3", token=token).to("cuda").eval()
        self.proc = Sam3Processor.from_pretrained("facebook/sam3", token=token)
        cache.commit()
        self.torch = torch

    @modal.method()
    def find(self, images: list[dict], prompts: list[str] = list(PROMPTS), threshold: float = 0.4) -> list[dict]:
        """images: [{"id", "jpeg": bytes}] -> [{"id", "size": [w, h], "hits": [{"prompt", "score", "box": [x0, y0, x1, y1]}]}]"""
        import io
        from PIL import Image
        out = []
        for im in images:
            pic = Image.open(io.BytesIO(im["jpeg"])).convert("RGB")
            hits = []
            for p in prompts:
                inputs = self.proc(images=pic, text=p, return_tensors="pt").to("cuda")
                with self.torch.no_grad():
                    res = self.model(**inputs)
                r = self.proc.post_process_instance_segmentation(
                    res, threshold=threshold, mask_threshold=0.5, target_sizes=inputs.get("original_sizes").tolist())[0]
                for box, score in zip(r["boxes"].tolist(), r["scores"].tolist()):
                    hits.append({"prompt": p, "score": round(float(score), 3), "box": [round(v, 1) for v in box]})
            out.append({"id": im["id"], "size": list(pic.size), "hits": sorted(hits, key=lambda h: -h["score"])})
        return out


@app.local_entrypoint()
def boxes(photos: str, out: str):
    """Find the meter photo on every JPEG in a folder (upright copies); write the boxes to a JSON file."""
    import json
    from pathlib import Path
    items = [{"id": p.stem, "jpeg": p.read_bytes()} for p in sorted(Path(photos).glob("*.jpg"))]
    res = Sam().find.remote(items)
    Path(out).write_text(json.dumps(res, indent=1))
    for r in res:
        top = r["hits"][0] if r["hits"] else None
        print(f"{r['id']:20} {len(r['hits'])} hits; top {top}")
