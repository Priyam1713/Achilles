#!/usr/bin/env python3
"""Uniform isolated specialist worker.

Each dependency island runs this same small HTTP contract. Heavy imports/models are lazy,
so installation is one-shot while VRAM/RAM residency remains demand-driven.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

ROOT = Path(os.environ.get("SOAI_ROOT", Path(__file__).resolve().parents[1])).resolve()
MODEL_ROOT = Path(os.environ.get("SOAI_MODEL_DIR", ROOT / "models")).expanduser().resolve()
STATE_ROOT = Path(os.environ.get("SOAI_STATE_DIR", ROOT / "state")).expanduser().resolve()
CACHE: dict[str, Any] = {}


class InvokeRequest(BaseModel):
    model_id: str
    operation: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)


def model_path(model_id: str) -> str:
    path = MODEL_ROOT / model_id / "hf"
    if not path.exists():
        raise FileNotFoundError(f"checkpoint is not synced: {path}")
    return str(path)


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if hasattr(value, "tolist"):
        return value.tolist()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if hasattr(value, "model_dump"):
        return jsonable(value.model_dump())
    if is_dataclass(value):
        return jsonable(asdict(value))
    return str(value)


def get_sentence_model(model_id: str, cross: bool = False):
    key = f"st:{model_id}:{cross}"
    if key in CACHE:
        return CACHE[key]
    import torch

    if cross:
        from sentence_transformers import CrossEncoder

        kwargs: dict[str, Any] = {"device": "cuda" if torch.cuda.is_available() else "cpu"}
        # Preserve retrieval quality while fitting 8B rerankers on 12GB when bitsandbytes is available.
        if torch.cuda.is_available():
            try:
                from transformers import BitsAndBytesConfig

                kwargs["model_kwargs"] = {
                    "quantization_config": BitsAndBytesConfig(load_in_8bit=True)
                }
            except Exception:
                pass
        obj = CrossEncoder(model_path(model_id), **kwargs)
    else:
        from sentence_transformers import SentenceTransformer

        obj = SentenceTransformer(
            model_path(model_id), device="cuda" if torch.cuda.is_available() else "cpu"
        )
    CACHE[key] = obj
    return obj


def retrieval(req: InvokeRequest) -> Any:
    if req.model_id == "gliner2-multi-v1":
        from gliner2 import GLiNER2

        model = CACHE.get(req.model_id)
        if model is None:
            model = GLiNER2.from_pretrained(model_path(req.model_id))
            CACHE[req.model_id] = model
        if req.operation == "__prewarm__":
            return {"loaded": req.model_id}
        text = req.inputs["text"]
        if req.operation == "extract_entities":
            return model.extract_entities(text, req.inputs["labels"])
        if req.operation == "classify":
            return model.classify_text(text, req.inputs["labels"])
        if req.operation == "extract_json":
            # GLiNER2 accepts a schema-like mapping for structured extraction.
            return model.extract_json(text, req.inputs["schema"])
        raise ValueError(f"unsupported GLiNER2 operation: {req.operation}")

    if req.operation == "__prewarm__":
        cross = "reranker" in req.model_id
        get_sentence_model(req.model_id, cross=cross)
        return {"loaded": req.model_id}
    if req.operation == "embed":
        model = get_sentence_model(req.model_id, cross=False)
        values = req.inputs.get("items", req.inputs.get("texts"))
        if values is None:
            raise ValueError("embed requires inputs.items or inputs.texts")
        return model.encode(
            values, normalize_embeddings=bool(req.options.get("normalize", True))
        ).tolist()
    if req.operation == "rerank":
        model = get_sentence_model(req.model_id, cross=True)
        query = req.inputs["query"]
        candidates = req.inputs["candidates"]
        pairs = [(query, c) for c in candidates]
        scores = model.predict(pairs)
        ranked = sorted(
            [
                {"index": i, "score": float(s), "candidate": candidates[i]}
                for i, s in enumerate(scores)
            ],
            key=lambda x: x["score"],
            reverse=True,
        )
        return ranked
    raise ValueError(f"unsupported retrieval operation: {req.operation}")


def qwen_asr(req: InvokeRequest) -> Any:
    if req.model_id == "whisper-large-v3-turbo":
        from transformers import pipeline

        pipe = CACHE.get(req.model_id)
        if pipe is None:
            pipe = pipeline(
                "automatic-speech-recognition", model=model_path(req.model_id), device=0
            )
            CACHE[req.model_id] = pipe
        if req.operation == "__prewarm__":
            return {"loaded": req.model_id}
        return pipe(
            req.inputs["audio"], return_timestamps=req.options.get("return_timestamps", False)
        )

    if req.model_id == "qwen3-forced-aligner-0.6b":
        import torch
        from qwen_asr import Qwen3ForcedAligner

        aligner = CACHE.get(req.model_id)
        if aligner is None:
            aligner = Qwen3ForcedAligner.from_pretrained(
                model_path(req.model_id), device_map="cuda:0", dtype=torch.bfloat16
            )
            CACHE[req.model_id] = aligner
        if req.operation == "__prewarm__":
            return {"loaded": req.model_id}
        if req.operation != "align":
            raise ValueError("Qwen forced aligner supports align")
        return aligner.align(
            audio=req.inputs["audio"],
            text=req.inputs["text"],
            language=req.inputs.get("language", req.options.get("language", "English")),
        )

    if req.model_id == "qwen3-asr-1.7b":
        import torch
        from qwen_asr import Qwen3ASRModel

        model = CACHE.get(req.model_id)
        if model is None:
            aligner_path = MODEL_ROOT / "qwen3-forced-aligner-0.6b" / "hf"
            model = Qwen3ASRModel.from_pretrained(
                model_path(req.model_id),
                forced_aligner=str(aligner_path) if aligner_path.exists() else None,
                device_map="cuda:0",
                dtype=torch.bfloat16,
                max_inference_batch_size=1,
            )
            CACHE[req.model_id] = model
        if req.operation == "__prewarm__":
            return {"loaded": req.model_id}
        if req.operation not in {"transcribe", "asr"}:
            raise ValueError("Qwen3-ASR supports transcribe/asr")
        return model.transcribe(
            audio=req.inputs["audio"],
            context=req.options.get("context", ""),
            language=req.options.get("language"),
            return_time_stamps=bool(req.options.get("return_timestamps", False)),
        )
    raise ValueError(f"unsupported ASR model: {req.model_id}")


def voxcpm(req: InvokeRequest) -> Any:
    if req.operation not in {"tts", "synthesize", "__prewarm__"}:
        raise ValueError("VoxCPM2 supports tts/synthesize")
    import soundfile as sf
    from voxcpm import VoxCPM

    model = CACHE.get(req.model_id)
    if model is None:
        model = VoxCPM.from_pretrained(model_path(req.model_id), load_denoiser=False)
        CACHE[req.model_id] = model
    if req.operation == "__prewarm__":
        return {"loaded": req.model_id}
    kwargs = {
        "text": req.inputs["text"],
        "cfg_value": float(req.options.get("cfg_value", 2.0)),
        "inference_timesteps": int(req.options.get("inference_timesteps", 10)),
        "seed": int(req.options.get("seed", 42)),
    }
    for name in ("reference_wav_path", "prompt_wav_path", "prompt_text"):
        if req.inputs.get(name):
            kwargs[name] = req.inputs[name]
    wav = model.generate(**kwargs)
    out_dir = STATE_ROOT / "artifacts" / "audio"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / req.options.get("filename", "tts.wav")
    sf.write(out, wav, model.tts_model.sample_rate)
    return {"path": str(out), "sample_rate": int(model.tts_model.sample_rate)}


def paddle(req: InvokeRequest) -> Any:
    if req.operation not in {"ocr", "document_parse", "__prewarm__"}:
        raise ValueError("Paddle worker supports ocr/document_parse")
    from paddleocr import PaddleOCRVL

    pipeline = CACHE.get("paddle")
    if pipeline is None:
        # Local pipeline keeps document layout and VLM inside the isolated worker.
        pipeline = PaddleOCRVL(vl_rec_model_dir=model_path(req.model_id))
        CACHE["paddle"] = pipeline
    if req.operation == "__prewarm__":
        return {"loaded": req.model_id}
    results = list(pipeline.predict(input=req.inputs["path"]))
    out_dir = STATE_ROOT / "artifacts" / "documents"
    out_dir.mkdir(parents=True, exist_ok=True)
    rendered = []
    for i, res in enumerate(results):
        try:
            res.save_to_json(save_path=out_dir)
        except Exception:
            pass
        try:
            res.save_to_markdown(save_path=out_dir)
        except Exception:
            pass
        rendered.append({"page": i, "repr": str(res)})
    return {"pages": rendered, "artifact_dir": str(out_dir)}


def vision(req: InvokeRequest) -> Any:
    if req.model_id == "rf-detr-large":
        from rfdetr import RFDETRLarge

        model = CACHE.get(req.model_id)
        if model is None:
            files = list(Path(model_path(req.model_id)).rglob("*.pth")) + list(
                Path(model_path(req.model_id)).rglob("*.pt")
            )
            model = RFDETRLarge(pretrain_weights=str(files[0])) if files else RFDETRLarge()
            CACHE[req.model_id] = model
        if req.operation == "__prewarm__":
            return {"loaded": req.model_id}
        det = model.predict(req.inputs["image"], threshold=float(req.options.get("threshold", 0.5)))
        data = {
            "xyxy": getattr(det, "xyxy", []),
            "confidence": getattr(det, "confidence", []),
            "class_id": getattr(det, "class_id", []),
            "data": getattr(det, "data", {}),
        }
        return jsonable(data)
    if req.model_id == "rf-detr-keypoint":
        from rfdetr import RFDETRKeypointPreview

        model = CACHE.get(req.model_id)
        if model is None:
            model = RFDETRKeypointPreview()
            CACHE[req.model_id] = model
        if req.operation == "__prewarm__":
            return {"loaded": req.model_id}
        return jsonable(
            model.predict(req.inputs["image"], threshold=float(req.options.get("threshold", 0.5)))
        )
    if req.model_id == "depth-anything-3":
        from depth_anything_3.api import DepthAnything3

        model = CACHE.get(req.model_id)
        if model is None:
            model = DepthAnything3.from_pretrained(model_path(req.model_id))
            CACHE[req.model_id] = model
        if req.operation == "__prewarm__":
            return {"loaded": req.model_id}
        prediction = model.inference([req.inputs["image"]])
        # Full dense arrays can be enormous. Return structured metadata unless explicitly requested.
        if req.options.get("include_arrays"):
            return jsonable(prediction)
        result = {}
        for key in ("depth", "conf", "extrinsics", "intrinsics"):
            val = getattr(prediction, key, None)
            if val is not None:
                result[key] = {
                    "shape": list(getattr(val, "shape", [])),
                    "dtype": str(getattr(val, "dtype", "")),
                }
        return result
    raise ValueError(f"unsupported vision model: {req.model_id}")


def science(req: InvokeRequest) -> Any:
    if req.model_id == "chronos-2" and req.operation in {"forecast", "__prewarm__"}:
        import pandas as pd
        from chronos import Chronos2Pipeline

        pipe = CACHE.get(req.model_id)
        if pipe is None:
            pipe = Chronos2Pipeline.from_pretrained(model_path(req.model_id), device_map="cuda")
            CACHE[req.model_id] = pipe
        if req.operation == "__prewarm__":
            return {"loaded": req.model_id}
        context = pd.DataFrame(req.inputs["context"])
        future = (
            pd.DataFrame(req.inputs["future"]) if req.inputs.get("future") is not None else None
        )
        pred = pipe.predict_df(
            context,
            future_df=future,
            prediction_length=int(req.inputs["prediction_length"]),
            quantile_levels=req.options.get("quantile_levels", [0.1, 0.5, 0.9]),
            id_column=req.options.get("id_column", "id"),
            timestamp_column=req.options.get("timestamp_column", "timestamp"),
            target=req.options.get("target", "target"),
        )
        return pred.to_dict(orient="records")
    raise ValueError(f"unsupported science operation: {req.model_id}/{req.operation}")


def tabpfn(req: InvokeRequest) -> Any:
    import numpy as np

    if req.operation not in {"classify", "regress"}:
        raise ValueError("TabPFN worker supports classify/regress")
    if req.operation == "classify":
        from tabpfn import TabPFNClassifier

        model = TabPFNClassifier(
            model_path=req.model_id if False else None
        )  # package resolves synced cache if configured
    else:
        from tabpfn import TabPFNRegressor

        model = TabPFNRegressor()
    model.fit(np.asarray(req.inputs["x_train"]), np.asarray(req.inputs["y_train"]))
    pred = model.predict(np.asarray(req.inputs["x_test"]))
    return pred.tolist()


HANDLERS = {
    "retrieval": retrieval,
    "qwen_asr": qwen_asr,
    "voxcpm": voxcpm,
    "paddleocr": paddle,
    "vision": vision,
    "science_general": science,
    "tabpfn": tabpfn,
}


def build_app(worker: str) -> FastAPI:
    app = FastAPI(title=f"SOAI specialist: {worker}")

    @app.get("/health")
    async def health():
        return {"ok": True, "worker": worker, "loaded": sorted(CACHE)}

    @app.post("/invoke")
    async def invoke(req: InvokeRequest):
        handler = HANDLERS.get(worker)
        if handler is None:
            raise HTTPException(501, f"worker adapter not yet stable: {worker}")
        try:
            return {"ok": True, "result": jsonable(handler(req))}
        except Exception as exc:
            raise HTTPException(500, f"{type(exc).__name__}: {exc}") from exc

    @app.post("/unload")
    async def unload():
        CACHE.clear()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
        return {"ok": True}

    return app


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    import uvicorn

    uvicorn.run(build_app(args.worker), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
