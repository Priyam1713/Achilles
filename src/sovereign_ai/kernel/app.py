from __future__ import annotations

from dataclasses import dataclass

from sovereign_ai.agents.native_loop import NativeAgentLoop
from sovereign_ai.agents.registry import AgentLoopRegistry
from sovereign_ai.collaboration import CollaborationService, CollaborationStore
from sovereign_ai.computer.controller import ComputerController
from sovereign_ai.execution.broker import ExecutionBroker
from sovereign_ai.execution.workspaces import WorkspaceRegistry
from sovereign_ai.inference.broker import InferenceBroker
from sovereign_ai.inference.media import MediaBroker
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
from sovereign_ai.tools.registry import ToolRegistry
from sovereign_ai.transactions.manager import TransactionManager
from sovereign_ai.verification.engine import VerificationEngine
from sovereign_ai.watchers.bus import EventBus

from .agent_profiles import AgentProfileStore
from .approvals import ApprovalRequestStore
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
        workspace_leases = WorkspaceLeaseStore(state / "workspace_leases.db")
        capability_grants = CapabilityGrantStore(state / "capability_grants.db")
        execution = ExecutionBroker(policy, workspaces, workspace_leases, capability_grants)
        memory = MemoryStore(state / "memory.db")
        vector_store = LocalVectorStore(state / "memory-vectors.db")
        memory_indexer = MemoryIndexer(specialists, vector_store)
        text_vector = SpecialistVectorRetriever(specialists, vector_store)
        context = ContextBuilder(memory, text_vector=text_vector)
        verification = VerificationEngine()
        agent_loops = AgentLoopRegistry()
        agent_loops.register(
            "native", NativeAgentLoop(inference, execution, workspaces, events)
        )
        computer = ComputerController()
        transactions = TransactionManager(state / "transactions")
        event_bus = EventBus()
        tools = ToolRegistry()
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
        )
