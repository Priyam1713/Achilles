from __future__ import annotations

from sovereign_ai.execution.broker import ExecutionBroker
from sovereign_ai.execution.workspaces import WorkspaceRegistry

from .capabilities import (
    GenerateMediaTool,
    InvokeSpecialistTool,
    RememberTool,
    SearchMemoryTool,
    WebSearchTool,
)
from .dispatcher import ToolDispatcher
from .files import (
    DeleteFileTool,
    EditFileTool,
    GlobTool,
    GrepTool,
    ListDirectoryTool,
    ReadFileTool,
    WriteFileTool,
)
from .mcp_client import CallMCPToolTool, ListMCPToolsTool, load_mcp_servers
from .plan import UpdatePlanTool
from .registry import ToolRegistry
from .shell import RunCommandTool


def build_file_tools(
    workspaces: WorkspaceRegistry,
    execution: ExecutionBroker | None = None,
    registry: ToolRegistry | None = None,
) -> ToolDispatcher:
    """The minimum an agent needs to be a coding agent: read, search, write, edit, run.

    Kept separate from `build_standard_tools` so `NativeAgentLoop` can construct exactly
    this set on its own when it is built without a kernel (every existing test, the harness
    tournament, any embedding caller) and still be strictly more capable than the
    three-tool loop wave 6 audited.
    """
    dispatcher = ToolDispatcher(registry)
    # Registered first and unconditionally: keeping a plan needs no execution backend and
    # no grant, and a loop that cannot restate its objective after compaction is the
    # failure this tool exists to prevent.
    dispatcher.register(UpdatePlanTool(dispatcher.plans))
    dispatcher.register(ReadFileTool(workspaces, execution))
    dispatcher.register(ListDirectoryTool(workspaces, execution))
    dispatcher.register(GlobTool(workspaces, execution))
    dispatcher.register(GrepTool(workspaces, execution))
    if execution is not None:
        dispatcher.register(WriteFileTool(workspaces, execution))
        dispatcher.register(EditFileTool(workspaces, execution))
        dispatcher.register(DeleteFileTool(workspaces, execution))
        dispatcher.register(RunCommandTool(execution))
    return dispatcher


def build_standard_tools(
    *,
    workspaces: WorkspaceRegistry,
    execution: ExecutionBroker,
    specialists=None,
    media=None,
    memory=None,
    context=None,
    search_url: str = "http://127.0.0.1:8888",
    mcp_servers: dict | None = None,
    registry: ToolRegistry | None = None,
) -> ToolDispatcher:
    """Every capability the kernel can currently reach, as tools.

    This function is the concrete answer to research wave 8's reachability table, which
    found nineteen of twenty-one capability domains unreachable because `ToolRegistry` was
    empty and the agent loop had no dispatcher. Each optional argument that is supplied
    turns a whole domain on:

    * ``specialists`` -- OCR, ASR, TTS, embedding/rerank, detection, depth, forecasting,
      tabular and structured extraction, routed by capability so the kernel's hardware-aware
      scheduler still picks the checkpoint.
    * ``media`` -- image, video and music generation through the media runtime.
    * ``memory``/``context`` -- durable recall and (grant-gated) storage.
    * ``search_url`` -- the SearXNG instance this project deploys and, until now, never
      queried.

    Nothing here relaxes authority: every mutating tool clears
    `ExecutionBroker.authorize`, which is the same grant-then-policy path a shell command
    has always taken.
    """
    dispatcher = build_file_tools(workspaces, execution, registry)
    if specialists is not None:
        dispatcher.register(InvokeSpecialistTool(specialists, workspaces))
    if media is not None:
        dispatcher.register(GenerateMediaTool(media, execution))
    if context is not None:
        dispatcher.register(SearchMemoryTool(context, execution))
    if memory is not None:
        dispatcher.register(RememberTool(memory, execution))
    dispatcher.register(WebSearchTool(execution, search_url))
    # Only when an operator has written servers down. Registering these unconditionally
    # would put two tools in front of the model that can never do anything.
    servers = load_mcp_servers(mcp_servers)
    if servers:
        dispatcher.register(ListMCPToolsTool(servers, execution))
        dispatcher.register(CallMCPToolTool(servers, execution))
    return dispatcher
