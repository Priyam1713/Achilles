from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path

import httpx
import yaml


class SpecialistSupervisor:
    """Starts isolated WSL/Linux specialist workers on demand.

    The kernel never imports their ML stacks. A broken Paddle/NeMo/Transformers install
    therefore cannot poison the control plane or another specialist.
    """

    def __init__(self, root: str | Path | None = None, state_dir: str | Path | None = None):
        self.root = Path(root or Path.cwd()).resolve()
        self.state_dir = Path(state_dir or self.root / "state").resolve()
        self.config = yaml.safe_load((self.root / "configs/workers.yaml").read_text())["workers"]
        self.model_to_worker: dict[str, str] = {}
        for worker, spec in self.config.items():
            for model in spec.get("models", []):
                self.model_to_worker[model] = worker
        self._locks: dict[str, asyncio.Lock] = {w: asyncio.Lock() for w in self.config}

    def worker_for(self, model_id: str) -> str | None:
        return self.model_to_worker.get(model_id)

    def url(self, worker: str) -> str:
        return f"http://127.0.0.1:{int(self.config[worker]['port'])}"

    async def healthy(self, worker: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                r = await client.get(self.url(worker) + "/health")
                return r.status_code == 200
        except Exception:
            return False

    def _wsl_root(self) -> str:
        if os.name != "nt":
            return str(self.root)
        return subprocess.check_output(
            ["wsl", "wslpath", "-a", str(self.root)], text=True, timeout=5
        ).strip()

    def _env_root(self) -> str:
        configured = os.getenv("SOAI_ENV_DIR")
        if configured:
            return configured
        lock = self.state_dir / "worker-lock.json"
        if lock.exists():
            raw = json.loads(lock.read_text())
            if raw.get("env_root"):
                return raw["env_root"]
        return "$HOME/.local/share/sovereign-ai/envs"

    async def ensure(self, worker: str, timeout_s: float = 25.0) -> str:
        if worker not in self.config:
            raise KeyError(worker)
        if await self.healthy(worker):
            return self.url(worker)
        async with self._locks[worker]:
            if await self.healthy(worker):
                return self.url(worker)
            root = self._wsl_root()
            envroot = self._env_root()
            port = int(self.config[worker]["port"])
            if worker == "media":
                # WanGP has its own persistent worker and startup script.
                command = (
                    f"cd {shlex_quote(root)} && source scripts/runtime_env.sh && "
                    f"nohup ./scripts/start_wangp_worker.sh {shlex_quote(root)} "
                    f'> "$SOAI_STATE_DIR/wangp-worker.log" 2>&1 &'
                )
            else:
                py = f"{envroot}/{worker}/bin/python"
                command = (
                    f"cd {shlex_quote(root)} && source scripts/runtime_env.sh && "
                    f"test -x {shlex_quote(py)} && "
                    f"nohup {shlex_quote(py)} scripts/specialist_worker.py --worker {shlex_quote(worker)} --port {port} "
                    f'> "$SOAI_STATE_DIR/worker-{worker}.log" 2>&1 &'
                )
            if os.name == "nt":
                proc = await asyncio.create_subprocess_exec("wsl", "bash", "-lc", command)
            else:
                proc = await asyncio.create_subprocess_exec("bash", "-lc", command)
            rc = await proc.wait()
            if rc != 0:
                raise RuntimeError(f"failed to launch specialist worker {worker}: exit {rc}")
            deadline = asyncio.get_running_loop().time() + timeout_s
            while asyncio.get_running_loop().time() < deadline:
                if await self.healthy(worker):
                    return self.url(worker)
                await asyncio.sleep(0.4)
            raise RuntimeError(
                f"specialist worker {worker} did not become healthy; "
                f"inspect {self.state_dir / f'worker-{worker}.log'}"
            )

    async def unload(self, worker: str) -> None:
        if not await self.healthy(worker):
            return
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                await c.post(self.url(worker) + "/unload")
        except Exception:
            pass


def shlex_quote(s: str) -> str:
    import shlex

    # Preserve shell expansion for our known $HOME fallback only.
    if s.startswith("$HOME/"):
        return '"' + s + '"'
    return shlex.quote(s)
