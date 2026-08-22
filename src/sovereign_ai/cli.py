from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from sovereign_ai.api.server import create_app
from sovereign_ai.kernel.app import SovereignKernel
from sovereign_ai.kernel.secrets import SecretStore
from sovereign_ai.kernel.shadow_git import ShadowRepository
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
def run(
    task: str,
    workspace: str = typer.Option(".", help="Directory the agent may work in"),
    loop: str = typer.Option("native", help="Registered AgentLoop to drive"),
    max_steps: int = typer.Option(10, help="Step budget for this run"),
    approve: bool = typer.Option(
        False,
        "--approve",
        help="Treat this run as human-approved, allowing mutations policy would otherwise stop",
    ),
    subject: str = typer.Option(
        "cli-operator", help="Subject id whose CapabilityGrants apply to this run"
    ),
    capability: str = typer.Option("coding", help="Capability to route the model by"),
    mode: RoutingMode = RoutingMode.SMART,
    config_root: str = "./configs",
) -> None:
    """Give the system a task and watch it work.

    Research wave 7 recorded that **no surface in this repository could start work**: the
    desktop cancels, lists and resolves, and the only way to make the system do anything was
    an `@mention` in a collaboration room or a hand-written HTTP request. This is the missing
    front door (`D-026`).

    Each step prints as it happens rather than after the run, because on hardware measured at
    6-52 tok/s an undifferentiated wait is the worst possible presentation of our slowest
    property (`D-029`). Mutations still require a `CapabilityGrant` or `--approve`; this
    command is an entry point, not a new authority (`D-026`'s safety boundary).
    """
    kernel = SovereignKernel.build(config_root)
    if loop not in kernel.agent_loops.names():
        console.print(
            f"[red]No agent loop named {loop!r}.[/red] Registered: "
            f"{', '.join(kernel.agent_loops.names()) or '(none)'}"
        )
        raise typer.Exit(code=2)
    agent_loop = kernel.agent_loops.get(loop)

    root = Path(workspace).expanduser().resolve(strict=False)
    if kernel.workspaces.resolve(root) is None:
        console.print(
            f"[red]{root} is not an approved workspace.[/red]\n"
            f"Knowing a path never grants authority to work in it. Register it first:\n"
            f"  [bold]sovereign workspace add {root}[/bold]"
        )
        raise typer.Exit(code=2)

    run_id = f"cli-{uuid.uuid4().hex[:12]}"
    state = {
        "run_id": run_id,
        "task": task,
        "workspace": str(root),
        "approved": approve,
        "agent_profile_id": subject,
        "capability": capability,
        "mode": mode.value,
        "max_steps": max_steps,
    }

    console.print(f"[bold]{task}[/bold]")
    console.print(f"[dim]run {run_id} · loop {loop} · {root} · budget {max_steps} steps"
                  f"{' · approved' if approve else ''}[/dim]\n")

    started = time.time()

    async def drive() -> dict:
        steps = 0
        while True:
            step_started = time.time()
            step = await agent_loop.next_step(state)
            steps += 1
            elapsed = time.time() - step_started
            _print_step(step, steps, elapsed)
            if step.done:
                return {"kind": step.kind, "payload": step.payload, "steps": steps}

    outcome = asyncio.run(drive())
    total = time.time() - started
    console.print(
        f"\n[dim]{outcome['steps']} steps · {total:.1f}s · "
        f"{total / max(1, outcome['steps']):.1f}s per step[/dim]"
    )
    if outcome["kind"] == "done":
        console.print(f"[bold green]done[/bold green] {outcome['payload'].get('summary', '')}")
    else:
        console.print(f"[bold yellow]{outcome['kind']}[/bold yellow] {json.dumps(outcome['payload'])[:600]}")
        raise typer.Exit(code=1)


def _print_step(step, index: int, elapsed: float) -> None:
    """One line per step, with the denial made loud.

    A denial is the single most important thing to surface: it is the kernel refusing an
    action, and burying it in a JSON blob is how an operator learns to stop reading.
    """
    payload = step.payload or {}
    if step.kind == "observation":
        tool = payload.get("tool")
        observation = payload.get("observation") or {}
        if observation.get("denied"):
            console.print(f"[red]{index:>3}. {tool} denied[/red] {observation.get('error', '')}")
        elif observation.get("error"):
            console.print(f"[yellow]{index:>3}. {tool} error[/yellow] {observation['error'][:300]}")
        else:
            summary = _summarise(observation)
            console.print(f"[cyan]{index:>3}. {tool}[/cyan] {summary} [dim]{elapsed:.1f}s[/dim]")
    elif step.kind == "unparsable":
        console.print(f"[yellow]{index:>3}. unparsable reply[/yellow] [dim]{elapsed:.1f}s[/dim]")
    elif step.kind == "done":
        console.print(f"[green]{index:>3}. done[/green] [dim]{elapsed:.1f}s[/dim]")
    else:
        console.print(f"[yellow]{index:>3}. {step.kind}[/yellow] {json.dumps(payload)[:200]}")


def _summarise(observation: dict) -> str:
    for key in ("path", "root", "query", "capability"):
        if key in observation:
            head = str(observation[key])
            for count_key in ("count", "total", "replacements", "bytes_written", "returncode"):
                if count_key in observation:
                    return f"{head} ({count_key}={observation[count_key]})"
            return head
    return json.dumps(observation)[:160]


@app.command("tools")
def list_tools(config_root: str = "./configs") -> None:
    """List the tools an agent can actually invoke.

    Named after the gap it closes: until the tool plane existed (F-047), the honest answer to
    "what can this system do?" was three read-only tools, regardless of what was installed.
    """
    kernel = SovereignKernel.build(config_root)
    table = Table("tool", "risk scope", "capabilities", "description")
    for spec in kernel.tool_dispatcher.specs():
        table.add_row(spec.id, spec.risk_scope, ", ".join(spec.capabilities), spec.description)
    console.print(table)
    console.print(f"[dim]{len(kernel.tool_dispatcher.names())} tools registered[/dim]")

@app.command()
def grant(
    subject: str,
    action: str = typer.Argument(..., help="write, execute, delete, read, network_get"),
    scope: str = typer.Argument("workspace", help="workspace, memory, host, public_web"),
    ttl_seconds: float = typer.Option(3600.0, help="How long this grant stays active"),
    granted_by: str = typer.Option("cli-operator", help="Who is authorising this"),
    config_root: str = "./configs",
) -> None:
    """Issue a time-bounded capability grant.

    Without this there was no terminal path to let an agent write anything: `sovereign run`
    correctly refuses a mutation from untrusted model output, and the only way to authorise
    one was an HTTP call. A grant is deliberately narrow and expiring -- subject, action,
    scope and a TTL -- which is the whole difference between authorising *this* and
    authorising the agent.
    """
    kernel = SovereignKernel.build(config_root)
    record = kernel.capability_grants.issue(
        subject, action, scope, granted_by, ttl_seconds=ttl_seconds
    )
    console.print(
        f"[green]granted[/green] {subject} -> {action}:{scope} "
        f"[dim]expires in {ttl_seconds:.0f}s · id {record.id}[/dim]"
    )


@app.command()
def grants(
    subject: str | None = typer.Option(None, help="Filter to one subject"),
    config_root: str = "./configs",
) -> None:
    """Show which authorisations are currently live."""
    kernel = SovereignKernel.build(config_root)
    if subject:
        rows = kernel.capability_grants.active_for_subject(subject)
    else:
        # There is no store-wide listing: grants are looked up per subject on purpose, since
        # "who holds authority right now" is a question about a subject, not a global feed.
        subjects = {profile.id for profile in kernel.agent_profiles.list()}
        rows = [g for s in sorted(subjects) for g in kernel.capability_grants.active_for_subject(s)]
    if not rows:
        console.print("[dim]no active grants[/dim] (pass --subject to check one directly)")
        return
    table = Table("subject", "action", "scope", "expires in", "granted by")
    now = time.time()
    for record in rows:
        table.add_row(
            record.subject_id,
            record.action,
            record.scope,
            f"{max(0.0, record.expires_at - now):.0f}s",
            record.granted_by,
        )
    console.print(table)


@app.command()
def approvals(
    approve: str | None = typer.Option(None, help="Approval id to approve"),
    deny: str | None = typer.Option(None, help="Approval id to deny"),
    reason: str = typer.Option("", help="Why -- recorded with the resolution"),
    resolver: str = typer.Option("cli-operator", help="Who is resolving"),
    config_root: str = "./configs",
) -> None:
    """List or resolve pending approvals.

    Wave 7 recorded that the approval card shows a risk badge and free text and not what it is
    actually approving (`D-028`). This surface at least prints the full request, evidence
    included, rather than a truncated summary -- an operator asked repeatedly to authorise
    things they cannot see learns to say yes without reading.
    """
    kernel = SovereignKernel.build(config_root)
    if approve and deny:
        console.print("[red]Pass either --approve or --deny, not both.[/red]")
        raise typer.Exit(code=2)
    if approve or deny:
        approval_id = approve or deny
        resolved, spawned = kernel.roster.resolve_approval(
            approval_id, resolver, bool(approve), reason or ("approved" if approve else "denied")
        )
        verdict = "[green]approved[/green]" if approve else "[red]denied[/red]"
        console.print(f"{verdict} {approval_id} [dim]{resolved.status}[/dim]")
        if spawned is not None:
            console.print(f"[dim]unblocked job {spawned.id} ({spawned.kind})[/dim]")
        return

    pending = kernel.approvals.list_pending()
    if not pending:
        console.print("[dim]nothing is waiting on you[/dim]")
        return
    for record in pending:
        console.print(f"[bold]{record.id}[/bold] [yellow]{record.risk}[/yellow]")
        console.print(f"  subject : {record.subject_id}")
        console.print(f"  action  : {record.action}:{record.scope}")
        console.print(f"  reason  : {record.reason}")
        if record.evidence:
            console.print(f"  evidence: {json.dumps(record.evidence)[:800]}")
        console.print(
            f"  [dim]sovereign approvals --approve {record.id}   "
            f"sovereign approvals --deny {record.id}[/dim]\n"
        )


@app.command()
def checkpoints(
    workspace: str = typer.Option(".", help="Workspace whose file history to inspect"),
    restore: str | None = typer.Option(None, help="Checkpoint sha to restore the files to"),
    limit: int = typer.Option(20, help="How many checkpoints to list"),
    config_root: str = "./configs",
) -> None:
    """List or restore the file-state checkpoints an agent left behind.

    These are shadow-git commits (`D-021`): a repository under `state/` that borrows the
    workspace as its work tree. Restoring puts files back with `checkout <sha> -- .`, so the
    later states stay in the log and the restore is itself undoable. Your own `.git` is never
    a participant.
    """
    kernel = SovereignKernel.build(config_root)
    root = Path(workspace).expanduser().resolve(strict=False)
    shadow = ShadowRepository(kernel.config.state_dir, root)
    if not ShadowRepository.available():
        console.print("[red]git is not installed, so no checkpoints exist.[/red]")
        raise typer.Exit(code=2)

    if restore:
        shadow.restore(restore)
        console.print(f"[green]restored[/green] {root} to {restore[:12]}")
        return

    history = shadow.history(limit=limit)
    if not history:
        console.print(f"[dim]no checkpoints recorded for {root}[/dim]")
        return
    table = Table("checkpoint", "label")
    for commit in history:
        table.add_row(commit.sha[:12], commit.label)
    console.print(table)
    console.print(
        f"[dim]restore with: sovereign checkpoints --workspace {root} "
        f"--restore {history[0].sha[:12]}[/dim]"
    )


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
