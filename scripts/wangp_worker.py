from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


class GenerateRequest(BaseModel):
    settings: dict[str, Any]
    timeout_s: float | None = None


class WanGPWorker:
    def __init__(self, wangp_root: Path, output_dir: Path):
        self.wangp_root = wangp_root.resolve()
        self.output_dir = output_dir.resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        sys.path.insert(0, str(self.wangp_root))
        try:
            from shared.api import init  # type: ignore
        except Exception as exc:  # pragma: no cover - hardware/runtime environment only
            raise RuntimeError(
                f"Unable to import WanGP shared.api from {self.wangp_root}: {exc}"
            ) from exc
        # Profile 4 is upstream's flexible low-VRAM path. SDPA is chosen because it is
        # the conservative quality-preserving attention backend; the kernel may benchmark
        # faster attention modes later before promoting them.
        self.session = init(
            root=self.wangp_root,
            output_dir=self.output_dir,
            cli_args=["--attention", "sdpa", "--profile", "4", "--perc-reserved-mem-max", "0.35"],
            console_output=True,
        )

    def models(self, include_availability: bool = True) -> list[dict[str, Any]]:
        return self.session.list_model_metadata(include_availability=include_availability)

    def schema(self, model_type: str) -> dict[str, Any] | None:
        return self.session.get_model_schema(model_type)

    def availability(self, model_type: str) -> dict[str, Any]:
        return self.session.get_model_availability(model_type)

    def generate(self, settings: dict[str, Any], timeout_s: float | None = None) -> dict[str, Any]:
        if not settings.get("model_type"):
            raise ValueError("settings.model_type is required")
        job = self.session.submit_task(settings)
        result = job.result(timeout=timeout_s)
        return {
            "success": bool(result.success),
            "cancelled": bool(getattr(result, "cancelled", False)),
            "generated_files": [str(x) for x in (result.generated_files or [])],
            "errors": [
                {
                    "message": str(getattr(err, "message", err)),
                    "type": str(getattr(err, "type", "generation_error")),
                }
                for err in (result.errors or [])
            ],
        }


def make_app(worker: WanGPWorker) -> FastAPI:
    app = FastAPI(title="Sovereign AI WanGP Worker", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "wangp_root": str(worker.wangp_root),
            "output_dir": str(worker.output_dir),
        }

    @app.get("/models")
    def models(include_availability: bool = True) -> dict[str, Any]:
        try:
            return {"models": worker.models(include_availability=include_availability)}
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/schema/{model_type}")
    def schema(model_type: str) -> dict[str, Any]:
        try:
            value = worker.schema(model_type)
            if value is None:
                raise HTTPException(status_code=404, detail="Unknown WanGP model_type")
            return value
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/availability/{model_type}")
    def availability(model_type: str) -> dict[str, Any]:
        try:
            return worker.availability(model_type)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/generate")
    def generate(req: GenerateRequest) -> dict[str, Any]:
        try:
            return worker.generate(req.settings, req.timeout_s)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    return app


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wangp-root", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7867)
    args = ap.parse_args()
    worker = WanGPWorker(Path(args.wangp_root), Path(args.output_dir))
    uvicorn.run(make_app(worker), host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
