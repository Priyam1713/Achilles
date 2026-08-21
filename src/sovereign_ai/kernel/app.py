from __future__ import annotations

from dataclasses import dataclass

from sovereign_ai.agents.registry import AgentLoopRegistry
from sovereign_ai.collaboration import CollaborationService, CollaborationStore
from sovereign_ai.computer.controller import ComputerController
from sovereign_ai.execution.broker import ExecutionBroker
from sovereign_ai.execution.workspaces import WorkspaceRegistry
from sovereign_ai.inference.broker import InferenceBroker
from sovereign_ai.inference.media import MediaBroker
from sovereign_ai.memory.context import ContextBuilder
from sovereign_ai.memory.graph import MemoryGraph
from sovereign_ai.memory.store import MemoryStore
from sovereign_ai.resources.arbiter import GPUArbiter
from sovereign_ai.resources.residency import ResidencyCoordinator
from sovereign_ai.resources.scheduler import ResourceScheduler
from sovereign_ai.specialists import SpecialistBroker, SpecialistSupervisor
from sovereign_ai.tools.registry import ToolRegistry
from sovereign_ai.transactions.manager import TransactionManager
from sovereign_ai.verification.engine import VerificationEngine
from sovereign_ai.watchers.bus import EventBus

from .benchmarks import BenchmarkStore
from .checkpoints import CheckpointStore
from .config import ConfigBundle
from .events import EventStore
from .jobs import JobStore
from .policy import PolicyEngine
from .registry import CapabilityRegistry
from .runs import RunStore
from .secrets import SecretStore


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
    inference: InferenceBroker
    media: MediaBroker
    specialists: SpecialistBroker
    specialist_supervisor: SpecialistSupervisor
    execution: ExecutionBroker
    workspaces: WorkspaceRegistry
    memory: MemoryStore
    context: ContextBuilder
    verification: VerificationEngine
    agent_loops: AgentLoopRegistry
    computer: ComputerController
    transactions: TransactionManager
    event_bus: EventBus
    gpu: GPUArbiter
    tools: ToolRegistry
    memory_graph: MemoryGraph
    residency: ResidencyCoordinator
    collaboration: CollaborationService

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
        inference = InferenceBroker(registry, scheduler, gpu)
        media = MediaBroker(registry, scheduler, gpu, residency)
        specialist_supervisor = SpecialistSupervisor(config.root.parent, state)
        specialists = SpecialistBroker(registry, scheduler, gpu, residency, specialist_supervisor)
        workspaces = WorkspaceRegistry(state / "workspaces.json")
        execution = ExecutionBroker(policy, workspaces)
        memory = MemoryStore(state / "memory.db")
        context = ContextBuilder(memory)
        verification = VerificationEngine()
        agent_loops = AgentLoopRegistry()
        computer = ComputerController()
        transactions = TransactionManager(state / "transactions")
        event_bus = EventBus()
        tools = ToolRegistry()
        memory_graph = MemoryGraph(state / "memory-graph.db")
        collaboration = CollaborationService(
            CollaborationStore(state / "collaboration.db"), config.collaboration
        )
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
            inference,
            media,
            specialists,
            specialist_supervisor,
            execution,
            workspaces,
            memory,
            context,
            verification,
            agent_loops,
            computer,
            transactions,
            event_bus,
            gpu,
            tools,
            memory_graph,
            residency,
            collaboration,
        )
