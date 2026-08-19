from __future__ import annotations

import json

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from sovereign_ai.api.server import create_app
from sovereign_ai.kernel.app import SovereignKernel
from sovereign_ai.kernel.secrets import SecretStore
from sovereign_ai.kernel.types import CapabilityRequest, RoutingMode
from sovereign_ai.resources.telemetry import snapshot

app = typer.Typer(no_args_is_help=True, help="Local Sovereign AI kernel control CLI")
console = Console()


@app.command()
def preflight(config_root: str = "./configs") -> None:
    """Validate configuration and inspect this machine without changing it."""
    kernel = SovereignKernel.build(config_root)
    snap = snapshot(kernel.config.state_dir)
    console.print("[bold green]Registry valid[/bold green]")
    console.print_json(data=snap.model_dump())
    console.print(f"Capabilities: {len(kernel.registry.capabilities())}")
    console.print(f"Models in manifest: {len(kernel.registry.models)}")


@app.command()
def route(
    capability: str, mode: RoutingMode = RoutingMode.SMART, config_root: str = "./configs"
) -> None:
    """Show why the kernel would select a model/engine for a capability."""
    kernel = SovereignKernel.build(config_root)
    decision = kernel.scheduler.route(CapabilityRequest(capability=capability, mode=mode))
    table = Table("rank", "model", "engine", "score", "quality", "reliability", "reason")
    for i, item in enumerate(decision.candidates, start=1):
        table.add_row(
            str(i),
            item.model_id,
            item.engine_id,
            f"{item.score:.3f}",
            f"{item.quality:.3f}",
            f"{item.reliability:.3f}",
            "; ".join(item.reasons),
        )
    console.print(table)
    if decision.warnings:
        console.print("Warnings:", decision.warnings)


@app.command()
def serve(config_root: str = "./configs") -> None:
    """Run the local kernel API."""
    kernel = SovereignKernel.build(config_root)
    system = kernel.config.system["system"]
    uvicorn.run(
        create_app(config_root),
        host=system.get("bind", "127.0.0.1"),
        port=int(system.get("port", 7788)),
    )


workspace = typer.Typer(help="Manage explicitly authorized agent workspaces")
app.add_typer(workspace, name="workspace")


@workspace.command("add")
def workspace_add(
    path: str, label: str | None = None, read_only: bool = False, config_root: str = "./configs"
) -> None:
    kernel = SovereignKernel.build(config_root)
    entry = kernel.workspaces.add(path, label=label, writable=not read_only)
    console.print_json(data=entry)


@workspace.command("remove")
def workspace_remove(path: str, config_root: str = "./configs") -> None:
    SovereignKernel.build(config_root).workspaces.remove(path)
    console.print("Workspace authorization removed")


@workspace.command("list")
def workspace_list(config_root: str = "./configs") -> None:
    console.print_json(data=SovereignKernel.build(config_root).workspaces.list())


secret = typer.Typer(help="Manage OS-backed secret handles")
app.add_typer(secret, name="secret")


@secret.command("set")
def secret_set(name: str, value: str = typer.Option(..., prompt=True, hide_input=True)) -> None:
    SecretStore().set(name, value)
    console.print(f"Stored [cyan]{SecretStore.handle(name)}[/cyan] in OS credential store")


@secret.command("delete")
def secret_delete(name: str) -> None:
    SecretStore().delete(name)
    console.print("Deleted")


@app.command("dump-manifest")
def dump_manifest(config_root: str = "./configs") -> None:
    kernel = SovereignKernel.build(config_root)
    console.print_json(
        json.dumps({k: v.model_dump(mode="json") for k, v in kernel.registry.models.items()})
    )


if __name__ == "__main__":
    app()
