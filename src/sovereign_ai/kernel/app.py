from __future__ import annotations

from dataclasses import dataclass

from sovereign_ai.agents.goose_loop import GooseAgentLoop
from sovereign_ai.agents.native_loop import NativeAgentLoop
from sovereign_ai.agents.opencode_loop import OpenCodeAgentLoop, resolve_opencode_binary
from sovereign_ai.agents.pi_loop import PiAgentLoop, resolve_pi_binary
from sovereign_ai.agents.registry import AgentLoopRegistry
from sovereign_ai.collaboration import CollaborationService, CollaborationStore
from sovereign_ai.computer.controller import ComputerController
from sovereign_ai.execution.broker import ExecutionBroker
from sovereign_ai.execution.workspaces import WorkspaceRegistry
from sovereign_ai.inference.broker import InferenceBroker
from sovereign_ai.inference.media import MediaBroker
from sovereign_ai.inference.remote_quota import RemoteQuotaLedger
from sovereign_ai.memory.context import ContextBuilder
from sovereign_ai.memory.graph import MemoryGraph
from sovereign_ai.memory.retrieval_adapter import MemoryIndexer, SpecialistVectorRetriever
from sovereign_ai.memory.store import MemoryStore
from sovereign_ai.memory.vector import LocalVectorStore
from sovereign_ai.resources.arbiter import GPUArbiter
from sovereign_ai.resources.residency import ResidencyCoordinator
from sovereign_ai.resources.scheduler import ResourceScheduler
from sovereign_ai.resources.workspace_leases import WorkspaceLeaseStore
from sovereign_ai.specialists import SpecialistBroker, SpecialistSupervisor
from sovereign_ai.tools.dispatcher import ToolDispatcher
from sovereign_ai.tools.registry import ToolRegistry
from sovereign_ai.tools.standard import build_standard_tools
from sovereign_ai.transactions.manager import TransactionManager
from sovereign_ai.verification.engine import VerificationEngine
from sovereign_ai.watchers.bus import EventBus

from .agent_profiles import AgentProfileStore
from .approvals import ApprovalRequestStore
from .auth import SessionAuth
from .benchmarks import BenchmarkStore
from .capability_grants import CapabilityGrantStore
from .checkpoints import CheckpointStore
from .config import ConfigBundle
from .delegations import DelegationStore
from .events import EventStore
from .jobs import JobStore
from .policy import PolicyEngine
from .presence import PresenceService
from .registry import CapabilityRegistry
from .roster import RosterService
from .runs import RunStore
from .secrets import SecretStore
from .skill_service import SkillService
from .skills import AgentEvaluationStore, SkillCandidateStore, SkillVersionStore
from .triggers import RecurringTriggerStore
from .workflow_service import WorkflowService
from .workflows import WorkflowDefinitionStore, WorkflowInstanceStore


@dataclass
class SovereignKernel:
    config: ConfigBundle
    registry: CapabilityRegistry
    events: EventStore
    jobs: JobStore
    runs: RunStore
    checkpoints: CheckpointStore
    benchmarks: BenchmarkStore
    policy: PolicyEngine
    secrets: SecretStore
    scheduler: ResourceScheduler
    remote_quota: RemoteQuotaLedger
    inference: InferenceBroker
    media: MediaBroker
    specialists: SpecialistBroker
    specialist_supervisor: SpecialistSupervisor
    execution: ExecutionBroker
    workspaces: WorkspaceRegistry
    memory: MemoryStore
    vector_store: LocalVectorStore
    memory_indexer: MemoryIndexer
    context: ContextBuilder
    verification: VerificationEngine
    agent_loops: AgentLoopRegistry
    computer: ComputerController
    transactions: TransactionManager
    event_bus: EventBus
    gpu: GPUArbiter
    tools: ToolRegistry
    tool_dispatcher: ToolDispatcher
    memory_graph: MemoryGraph
    residency: ResidencyCoordinator
    collaboration: CollaborationService
    agent_profiles: AgentProfileStore
    delegations: DelegationStore
    capability_grants: CapabilityGrantStore
    approvals: ApprovalRequestStore
    workspace_leases: WorkspaceLeaseStore
    roster: RosterService
    presence: PresenceService
    workflow_definitions: WorkflowDefinitionStore
    workflow_instances: WorkflowInstanceStore
    workflows: WorkflowService
    triggers: RecurringTriggerStore
    skill_candidates: SkillCandidateStore
    agent_evaluations: AgentEvaluationStore
    skill_versions: SkillVersionStore
    skills: SkillService

    @classmethod
    def build(cls, config_root: str | None = None) -> SovereignKernel:
        config = ConfigBundle(config_root)
        state = config.state_dir
        registry = CapabilityRegistry(config)
        errors = registry.validate()
        if errors:
            raise RuntimeError("Registry validation failed:\n" + "\n".join(errors))
        events = EventStore(state / "events.db")
        jobs = JobStore(state / "jobs.db")
        runs = RunStore(state / "runs.db")
        checkpoints = CheckpointStore(state / "checkpoints.db")
        benchmarks = BenchmarkStore(state / "benchmarks.db")
        policy = PolicyEngine(config)
        secrets = SecretStore()
        scheduler = ResourceScheduler(config, registry, benchmarks)
        gpu = GPUArbiter(
            int(config.system.get("resources", {}).get("max_concurrent_gpu_heavy_jobs", 1)),
            state_dir=state,
        )
        residency = ResidencyCoordinator()
        remote_quota = RemoteQuotaLedger(state / "remote_quota.db")
        inference = InferenceBroker(registry, scheduler, gpu, secrets, remote_quota)
        media = MediaBroker(registry, scheduler, gpu, residency)
        specialist_supervisor = SpecialistSupervisor(config.root.parent, state)
        specialists = SpecialistBroker(registry, scheduler, gpu, residency, specialist_supervisor)
        workspaces = WorkspaceRegistry(state / "workspaces.json")
        workspace_leases = WorkspaceLeaseStore(state / "workspace_leases.db")
        capability_grants = CapabilityGrantStore(state / "capability_grants.db")
        execution = ExecutionBroker(policy, workspaces, workspace_leases, capability_grants)
        memory = MemoryStore(state / "memory.db")
        vector_store = LocalVectorStore(state / "memory-vectors.db")
        memory_indexer = MemoryIndexer(specialists, vector_store)
        text_vector = SpecialistVectorRetriever(specialists, vector_store)
        context = ContextBuilder(memory, text_vector=text_vector)
        verification = VerificationEngine()
        tools = ToolRegistry()
        tool_dispatcher = build_standard_tools(
            registry=tools,
            workspaces=workspaces,
            execution=execution,
            specialists=specialists,
            media=media,
            memory=memory,
            context=context,
            search_url=str(
                config.system.get("search", {}).get("searxng_url", "http://127.0.0.1:8888")
            ),
            mcp_servers=config.mcp_servers,
        )
        agent_loops = AgentLoopRegistry(
            default_name=str(config.system.get("system", {}).get("default_agent_loop", "native"))
        )
        agent_loops.register(
            "native",
            NativeAgentLoop(
                inference,
                execution,
                workspaces,
                events,
                tools=tool_dispatcher,
                checkpoint_root=state,
            ),
        )
        # D-015: Goose is genuinely optional -- most installs of this project will never
        # have built it (it needs a Rust/Cargo toolchain most users won't have either),
        # so it is registered only when the compiled binary actually exists, the same
        # "runtime truth over manifest assumption" rule InferenceBroker already applies to
        # engines (FIXES.md, broker.py docstring).
        llama_cpp_engine = registry.engines.get("llama_cpp")
        goose_binary = config.runtime_dir / "goose" / "bin" / "goose"
        if goose_binary.exists():
            if llama_cpp_engine and llama_cpp_engine.base_url:
                agent_loops.register(
                    # Same model NativeAgentLoop's own default `capability="coding"`
                    # resolves to (configs/models.yaml), so a harness-tournament run
                    # comparing the two loops is comparing loops, not models.
                    "goose",
                    GooseAgentLoop(str(goose_binary), llama_cpp_engine.base_url, "qwen38-27b"),
                )
        # Same runtime-truth rule as Goose: registered only when a *working* binary
        # exists, so an install without it has one fewer loop rather than a loop that
        # fails at first use. `resolve_opencode_binary()` rather than `shutil.which()`
        # because npm's shim is frequently shadowed by a stale symlink and the real
        # executable lives in a platform-specific optional dependency.
        opencode_binary = resolve_opencode_binary()
        if opencode_binary and llama_cpp_engine and llama_cpp_engine.base_url:
            agent_loops.register(
                "opencode",
                OpenCodeAgentLoop(opencode_binary, llama_cpp_engine.base_url, "qwen38-27b"),
            )
        # Pi cannot be reached through the MCP bridge -- it has no MCP client by design --
        # so its adapter drives an in-process extension that calls the kernel's own HTTP
        # API instead, and therefore needs the API's URL and session token rather than just
        # the inference base URL.
        pi_binary = resolve_pi_binary()
        if pi_binary and llama_cpp_engine and llama_cpp_engine.base_url:
            system = config.system.get("system", {})
            agent_loops.register(
                "pi",
                PiAgentLoop(
                    pi_binary,
                    llama_cpp_engine.base_url,
                    "qwen38-27b",
                    kernel_url=f"http://{system.get('bind', '127.0.0.1')}:{system.get('port', 7788)}",
                    session_token=SessionAuth(state / "session.token").token,
                ),
            )
        computer = ComputerController()
        transactions = TransactionManager(state / "transactions")
        event_bus = EventBus()
        memory_graph = MemoryGraph(state / "memory-graph.db")
        collaboration = CollaborationService(
            CollaborationStore(state / "collaboration.db"), config.collaboration
        )
        agent_profiles = AgentProfileStore(state / "agent_profiles.db")
        delegations = DelegationStore(state / "delegations.db")
        approvals = ApprovalRequestStore(state / "approvals.db")
        roster = RosterService(agent_profiles, delegations, capability_grants, approvals, jobs, policy)
        presence = PresenceService(capability_grants, workspace_leases, delegations, jobs)
        workflow_definitions = WorkflowDefinitionStore(state / "workflow_definitions.db")
        workflow_instances = WorkflowInstanceStore(state / "workflow_instances.db")
        workflows = WorkflowService(workflow_definitions, workflow_instances, jobs)
        triggers = RecurringTriggerStore(state / "recurring_triggers.db")
        skill_candidates = SkillCandidateStore(state / "skill_candidates.db")
        agent_evaluations = AgentEvaluationStore(state / "agent_evaluations.db")
        skill_versions = SkillVersionStore(state / "skill_versions.db")
        skills = SkillService(runs, skill_candidates, agent_evaluations, skill_versions)
        return cls(
            config,
            registry,
            events,
            jobs,
            runs,
            checkpoints,
            benchmarks,
            policy,
            secrets,
            scheduler,
            remote_quota,
            inference,
            media,
            specialists,
            specialist_supervisor,
            execution,
            workspaces,
            memory,
            vector_store,
            memory_indexer,
            context,
            verification,
            agent_loops,
            computer,
            transactions,
            event_bus,
            gpu,
            tools,
            tool_dispatcher,
            memory_graph,
            residency,
            collaboration,
            agent_profiles,
            delegations,
            capability_grants,
            approvals,
            workspace_leases,
            roster,
            presence,
            workflow_definitions,
            workflow_instances,
            workflows,
            triggers,
            skill_candidates,
            agent_evaluations,
            skill_versions,
            skills,
        )
