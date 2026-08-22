# Contributing to Achilles

Achilles is a local, sovereign AI kernel meant to be run and adapted on hardware its authors
have never seen. That goal shapes every rule below.

## The two rules that are not negotiable

1. **Everything in the critical path must be open source and self-hostable.** Closed-source
   software, subscription-gated services and hosted commercial inference APIs are not
   candidates — not as defaults, not as fallbacks. Open *weights* under a non-OSI vendor
   licence are a separate category requiring an explicit, recorded, per-model decision. This
   is baseline invariant 8 in [knowledge/research.md](knowledge/research.md).
2. **The kernel owns authority; nothing else does.** A model, harness, UI, sandbox or protocol
   may propose. Policy, capability grants, approvals, leases and verification decide. A change
   that lets any of those bypass `PolicyEngine`, `CapabilityGrant` or the approval path will be
   rejected regardless of how much capability it adds.

## Before you write code

Read, in this order:

- [`README.md`](README.md) — what exists, and honestly what does not.
- [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) — the difference between
  implemented, installed and reachable.
- [`knowledge/research.md`](knowledge/research.md) — the decision ledger. Every architectural
  choice has a dated record with its reasoning, safety boundary and revisit trigger.
- [`docs/FIXES.md`](docs/FIXES.md) — known defects and the order they are being fixed in.

If your change contradicts a recorded decision, that is allowed — but say so, and propose the
superseding decision record rather than quietly diverging.

## Definition of done

A capability is not done when the code exists. It is done when:

- an agent can invoke it through the tool plane (`D-034`), or a human can through an
  authenticated surface;
- it is gated by the same policy path as everything else;
- it has a test that starts where a real caller starts and ends at a verified result;
- documentation says what it does *and* what it does not;
- `knowledge/research.md` records the decision if the change is architectural, and
  `docs/FIXES.md` records the evidence if it fixes a defect.

Claiming a capability that is installed but unreachable is the specific failure mode this
project has already made once, at scale. Do not repeat it.

## Development setup

```bash
uv sync
uv run pytest -q
uv run ruff check .
```

Windows hosts additionally use `Install.ps1` and `scripts/start.ps1`; a Linux install path is
in progress (`D-035`). Model downloads are large and are never required to run the test suite.

## Pull requests

- Keep them scoped to one change with its tests.
- Match the surrounding code's style; run `ruff` before submitting.
- Explain the safety boundary of anything that touches execution, secrets, memory scope,
  network egress or approvals.
- New dependencies need a licence, a reason and a rollback path.

## Reporting security issues

Do not open a public issue for a vulnerability. See [`SECURITY.md`](SECURITY.md).

## Licence

Contributions are accepted under the Apache License 2.0, the licence of this repository. By
submitting a contribution you confirm you have the right to license it that way.
