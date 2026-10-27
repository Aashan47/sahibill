"""Omnilingual ASR (Meta, Apache 2.0) on a Modal L4, for voice questions and for evaluation E7.

Two Meta speech models transcribe each clip independently: omniASR_LLM_7B_v2 (the answer) and
omniASR_LLM_1B_v2 (a second opinion). Their character-level disagreement is the uncertainty signal; the
threshold per language is set on the dev split, never the test split. Weights are fetched once into a
Modal volume by a CPU function; the GPU container scales to zero when idle.

Not run until the cost estimate is approved (spending rules in the build plan).
  modal run sahibill/speech/modal_asr.py::fetch_weights      # CPU only, once
  modal deploy sahibill/speech/modal_asr.py                    # serves transcribe()
"""
from __future__ import annotations

import modal

app = modal.App("sahibill-asr")
weights = modal.Volume.from_name("sahibill-asr-weights", create_if_missing=True)
# fairseq2n 0.6 (required by omnilingual-asr) pins torch==2.8.0; torchaudio must match it exactly,
# or an unpinned install pulls a CUDA 13 build that fails to load.
image = (modal.Image.debian_slim(python_version="3.11")
         .apt_install("curl")   # 0.2.0 declares Requires-Python <=3.12, excluding 3.12.x
         .apt_install("ffmpeg", "libsndfile1")
         .pip_install("torch==2.8.0", "torchaudio==2.8.0")
         .pip_install("omnilingual-asr==0.2.0", "soundfile", "pyarrow==20.0.0", "numpy<2"))
CACHE = "/weights"
MODELS = ("sahibill_omniASR_LLM_7B_v2", "sahibill_omniASR_LLM_1B_v2")   # local cards, see CARDS
LANG = {"urdu": "urd_Arab", "punjabi": "pnb_Arab", "sindhi": "snd_Arab", "pashto": "pus_Arab", "saraiki": "skr_Arab",
        "english": "eng_Latn"}


FILES = {  # Meta's own download links, from the model cards in omnilingual-asr (cards/models/rc_models_v2.yaml)
    "omniASR-LLM-7B-v2.pt": "https://dl.fbaipublicfiles.com/mms/omniASR-LLM-7B-v2.pt",
    "omniASR-LLM-1B-v2.pt": "https://dl.fbaipublicfiles.com/mms/omniASR-LLM-1B-v2.pt",
    "omniASR_tokenizer_written_v2.model": "https://dl.fbaipublicfiles.com/mms/omniASR_tokenizer_written_v2.model",
}
CARDS = f"""name: sahibill_omniASR_tokenizer_written_v2
tokenizer_family: char_tokenizer
tokenizer: file://{CACHE}/omniASR_tokenizer_written_v2.model
---
name: sahibill_omniASR_LLM_1B_v2
model_family: wav2vec2_llama
model_arch: 1b_v2
checkpoint: file://{CACHE}/omniASR-LLM-1B-v2.pt
tokenizer_ref: sahibill_omniASR_tokenizer_written_v2
---
name: sahibill_omniASR_LLM_7B_v2
model_family: wav2vec2_llama
model_arch: 7b_v2
checkpoint: file://{CACHE}/omniASR-LLM-7B-v2.pt
tokenizer_ref: sahibill_omniASR_tokenizer_written_v2
"""


@app.function(image=image, volumes={CACHE: weights}, timeout=3600, cpu=1, memory=2048)
def fetch_weights():
    """Download the checkpoints straight from Meta's server into the volume (small CPU, resumable)."""
    import os
    import subprocess
    out = {}
    for name, url in FILES.items():
        dst = os.path.join(CACHE, name)
        subprocess.run(["curl", "-sSfL", "-C", "-", "-o", dst, url], check=True)
        weights.commit()
        out[name] = os.path.getsize(dst)
    return out


@app.cls(image=image, gpu=["L4", "A10G"],
          volumes={CACHE: weights}, timeout=1800, scaledown_window=120)   # A10G (24 GB) when no L4 is free
class ASR:
    @modal.enter()
    def load(self):
        import os
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        cards = "/tmp/fairseq2-cards"
        os.makedirs(cards, exist_ok=True)
        with open(os.path.join(cards, "sahibill.yaml"), "w") as fh:
            fh.write(CARDS)
        os.environ["FAIRSEQ2_USER_ASSET_DIR"] = cards     # local cards point at the volume's files
        from omnilingual_asr.models.inference.pipeline import ASRInferencePipeline
        self.pipes = {m: ASRInferencePipeline(model_card=m) for m in MODELS}

    @modal.method()
    def ping(self) -> bool:
        """Nothing to do: calling it starts a container, which loads both models (used to warm up before a question)."""
        return True

    @modal.method()
    def transcribe(self, clips: list[dict], language: str) -> list[dict]:
        """clips: [{"id", "audio": bytes, "format": "mp3"|"wav"|"flac"}]. Returns both models' text per clip."""
        import os
        import subprocess
        import tempfile
        import time
        lang = LANG[language]
        paths = []
        tmp = tempfile.mkdtemp()
        for c in clips:   # the pipeline's own decoder reads Common Voice mp3 as empty: convert with ffmpeg first
            src = os.path.join(tmp, f"{c['id']}.{c.get('format', 'wav')}")
            with open(src, "wb") as fh:
                fh.write(c["audio"])
            p = os.path.join(tmp, f"{c['id']}.16k.wav")
            subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", src, "-ac", "1", "-ar", "16000", p],
                           check=True)
            paths.append(p)
        out = {c["id"]: {"id": c["id"]} for c in clips}
        for m, pipe in self.pipes.items():
            t = time.time()
            texts = pipe.transcribe(paths, lang=[lang] * len(paths), batch_size=8)
            for c, txt in zip(clips, texts):
                out[c["id"]][m] = txt
            for c in clips:
                out[c["id"]].setdefault("seconds", {})[m] = round((time.time() - t) / len(clips), 2)
        return list(out.values())

    @modal.method()
    def run_files(self, items: list[dict], lang: str | None, chunk: bool = False) -> dict:
        """E7: items [{"id", "path" (in the volume), "seconds"}]; lang a model code or None (no conditioning).
        Clips are batched in order of length; with chunk, a clip over 35 s is cut into equal pieces under 35 s
        (the LLM models accept only clips under 40 s) and the pieces' text is joined in order."""
        import math
        import os
        import subprocess
        import tempfile
        import time
        import torch
        t0 = time.time()
        tmp = tempfile.mkdtemp()
        pieces = []                  # (item id, piece index, wav path, seconds)
        for it in items:
            src, base = it["path"], os.path.join(tmp, it["id"])
            secs = it.get("seconds") or float(subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src],
                capture_output=True, text=True, check=True).stdout)
            n = math.ceil(secs / 35) if chunk and secs > 35 else 1
            for k in range(n):
                p = f"{base}.{k}.wav"
                cut = ["-ss", f"{k * secs / n:.3f}", "-t", f"{secs / n:.3f}"] if n > 1 else []
                subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", src, *cut, "-ac", "1", "-ar", "16000", p],
                               check=True)
                pieces.append((it["id"], k, p, secs / n))
        pieces.sort(key=lambda x: x[3])
        batches, cur = [], []        # both models stay on the card (about 20 of 22 GB): at most 30 s of audio per batch
        for p in pieces:
            if cur and (len(cur) == 8 or sum(q[3] for q in cur) + p[3] > 30):
                batches.append(cur)
                cur = []
            cur.append(p)
        batches += [cur] if cur else []
        texts, oom = {m: {} for m in self.pipes}, 0
        for m, pipe in self.pipes.items():
            for b in batches:
                try:
                    got = pipe.transcribe([p[2] for p in b], lang=[lang] * len(b) if lang else None, batch_size=len(b))
                except torch.OutOfMemoryError:
                    torch.cuda.empty_cache()
                    got = []
                    for p in b:          # one clip at a time; a clip that still does not fit is left empty
                        try:
                            got += pipe.transcribe([p[2]], lang=[lang] if lang else None, batch_size=1)
                        except torch.OutOfMemoryError:
                            torch.cuda.empty_cache()
                            got.append("")
                            oom += 1
                for p, txt in zip(b, got):
                    texts[m][(p[0], p[1])] = txt
        rows = []
        for it in items:
            row = {"id": it["id"]}
            for m in self.pipes:
                ks = sorted(k for (i, k) in texts[m] if i == it["id"])
                row[m] = " ".join(texts[m][(it["id"], k)] for k in ks)
            rows.append(row)
        return {"rows": rows, "gpu": torch.cuda.get_device_name(0), "container_seconds": round(time.time() - t0, 1),
                "pieces_out_of_memory": oom}


EVAL = f"{CACHE}/eval"
FLEURS = [(code, split) for code in ("ur_pk", "sd_in", "ps_af") for split in ("dev", "test")]
OMNI = [("pnb_Arab", split) for split in ("dev", "test")]


@app.function(image=image, volumes={CACHE: weights}, timeout=3600, cpu=2, memory=4096)
def fetch_eval():
    """CPU: fetch the public E7 sets (FLEURS dev and test audio; the Omnilingual corpus pnb_Arab dev and test)
    into the volume. Omnilingual audio is written out as files with a manifest of ids, transcripts and lengths."""
    import json
    import os
    import subprocess
    import pyarrow.parquet as pq
    hf = "https://huggingface.co/datasets"
    for code, split in FLEURS:
        d = f"{EVAL}/fleurs/{code}/{split}"
        if not os.path.isdir(d) or not os.listdir(d):
            os.makedirs(d, exist_ok=True)
            tar = f"/tmp/{code}.{split}.tar.gz"
            subprocess.run(["curl", "-sSfL", "-o", tar, f"{hf}/google/fleurs/resolve/main/data/{code}/audio/{split}.tar.gz"], check=True)
            subprocess.run(["tar", "-xzf", tar, "-C", d, "--strip-components=1"], check=True)
            os.remove(tar)
            weights.commit()
    out = {}
    for code, split in OMNI:
        d = f"{EVAL}/omni/{code}/{split}"
        os.makedirs(d, exist_ok=True)
        pqf = f"/tmp/{code}.{split}.parquet"
        subprocess.run(["curl", "-sSfL", "-o", pqf,
                        f"{hf}/facebook/omnilingual-asr-corpus/resolve/main/data/{code}/{split}-00000-of-00001.parquet"], check=True)
        rows = []
        for i, r in enumerate(pq.read_table(pqf).to_pylist()):
            rid = f"{code}-{split}-{i:03d}-{r['speaker_id']}-{r['prompt_id']}-{r['segment_id']}"
            ext = os.path.splitext((r["audio"] or {}).get("path") or "x.wav")[1] or ".wav"
            with open(f"{d}/{rid}{ext}", "wb") as fh:
                fh.write(r["audio"]["bytes"])
            rows.append({"id": rid, "file": f"{rid}{ext}", "ref": r["raw_text"], "seconds": r["duration"]})
        with open(f"{d}/manifest.json", "w") as fh:
            json.dump(rows, fh, ensure_ascii=False)
        os.remove(pqf)
        weights.commit()
        out[f"{code}/{split}"] = len(rows)
    out.update({f"{c}/{s}": len(os.listdir(f"{EVAL}/fleurs/{c}/{s}")) for c, s in FLEURS})
    return out


@app.local_entrypoint()
def timing(clips_dir: str = "", n: int = 10, language: str = "saraiki"):
    """Time both models on n dev clips: modal run sahibill/speech/modal_asr.py::timing --clips-dir <dir>"""
    import csv
    import json
    import os
    rows = list(csv.DictReader(open(os.path.join(clips_dir, "dev.tsv")), delimiter="\t"))[:n]
    clips = [{"id": r["path"].rsplit(".", 1)[0], "format": "mp3",
              "audio": open(os.path.join(clips_dir, "clips", r["path"]), "rb").read(), "ref": r["sentence"]} for r in rows]
    refs = {c["id"]: c.pop("ref") for c in clips}
    out = ASR().transcribe.remote(clips, language)
    for o in out:
        o["reference"] = refs[o["id"]]
    print(json.dumps(out, ensure_ascii=False, indent=1))


RATE = {"L4": 0.000222, "A10": 0.000306}     # US$ per GPU second (Modal pricing page), A10G when not an L4
ORDER = [("urdu", "dev"), ("urdu", "test"), ("saraiki", "test"), ("sindhi", "test"), ("pashto", "test"),
         ("punjabi", "test"), ("saraiki", "dev"), ("sindhi", "dev"), ("pashto", "dev"), ("punjabi", "dev"),
         ("pashto", "test-unconditioned")]


@app.local_entrypoint()
def e7(manifest: str, out_dir: str, cv_clips: str, budget_usd: float = 2.20, batch: int = 150, only: str = ""):
    """E7 on the fixed sets, in the pre-registered order; stops before a batch that would pass the budget.
    modal run sahibill/speech/modal_asr.py::e7 --manifest <e7-manifest.json> --out-dir <dir> --cv-clips <clips dir>"""
    import json
    import os
    import time
    m = json.load(open(manifest))
    sets = {(s["language"], s["split"]): s for s in m["sets"]}
    os.makedirs(out_dir, exist_ok=True)
    cv_files = sorted({i["file"] for s in m["sets"] if s["corpus"] == "cv" for i in s["items"]})
    try:
        have = {e.path.rsplit("/", 1)[-1] for e in weights.listdir("/eval/cv/skr")}
    except Exception:  # noqa: BLE001  (not uploaded yet)
        have = set()
    if set(cv_files) - have:
        with weights.batch_upload(force=True) as up:
            for f in sorted(set(cv_files) - have):
                up.put_file(os.path.join(cv_clips, f), f"/eval/cv/skr/{f}")
    print("fetch_eval:", fetch_eval.remote())
    for s in m["sets"]:
        if s["corpus"] == "omni":
            s["items"] = json.loads(b"".join(weights.read_file(f"/eval/omni/{s['code']}/{s['split']}/manifest.json")))
    spent, audio_done, asr = 0.0, 0.0, ASR()
    logf = os.path.join(out_dir, "run-log.jsonl")
    for line in open(logf) if os.path.exists(logf) else []:     # a resumed run keeps counting from before
        e = json.loads(line)
        spent, audio_done = e.get("spent_est", spent), e.get("audio_done", audio_done)
    log = open(logf, "a")
    order = [tuple(x.split("-", 1)) for x in only.split(",")] if only else ORDER   # e.g. "saraiki-dev,sindhi-dev"
    for lang, split in order:
        s = sets[(lang, split.split("-")[0])]
        code = None if split.endswith("unconditioned") else LANG[lang]
        root = {"fleurs": f"{EVAL}/fleurs/{s['code']}/{s['split']}", "cv": f"{EVAL}/cv/skr",
                "omni": f"{EVAL}/omni/{s['code']}/{s['split']}"}[s["corpus"]]
        dst = os.path.join(out_dir, f"{lang}-{split}.json")
        done = json.load(open(dst)) if os.path.exists(dst) else []
        seen = {r["id"] for r in done}
        todo = [i for i in s["items"] if i["id"] not in seen]
        for k in range(0, len(todo), batch):
            part = todo[k:k + batch]
            est = sum(i.get("seconds") or 0 for i in part) * (spent / audio_done if audio_done else 0)
            if spent + est > budget_usd:
                print(f"STOP: spent ${spent:.3f}; the next batch (est ${est:.3f}) would pass ${budget_usd} ({lang} {split})")
                log.write(json.dumps({"stop": True, "spent_est": spent, "audio_done": audio_done, "before": f"{lang}-{split}"}) + "\n")
                return
            t = time.time()
            res = asr.run_files.remote([{"id": i["id"], "path": f"{root}/{i['file']}", "seconds": i.get("seconds")} for i in part],
                                       code, chunk=s["corpus"] == "omni")
            wall = time.time() - t
            rate = RATE["L4"] if "L4" in res["gpu"] else RATE["A10"]
            spent += wall * rate
            audio_done += sum(i.get("seconds") or 0 for i in part)
            refs = {i["id"]: i for i in part}
            for r in res["rows"]:
                r.update(reference=refs[r["id"]]["ref"], seconds_audio=refs[r["id"]].get("seconds"),
                         language=lang, split=split, model_lang=code)
            done += res["rows"]
            json.dump(done, open(dst, "w"), ensure_ascii=False)
            log.write(json.dumps({"set": f"{lang}-{split}", "n": len(part), "gpu": res["gpu"], "wall_s": round(wall, 1),
                                  "container_s": res["container_seconds"], "oom_pieces": res.get("pieces_out_of_memory"), "spent_est": round(spent, 4),
                                  "audio_done": round(audio_done, 1)}) + "\n")
            log.flush()
            print(f"{lang:8} {split:20} +{len(part):4}  {res['gpu']:24} {wall:7.1f}s  est ${spent:.3f}")
    print(f"done, est ${spent:.3f}")
