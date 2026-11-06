# V1 gate attestations

Human operators place `<gate_id>.json` here (ids in `entropytrade.operations.v1_gates.GATES`) with
`gate_id`, `attested_by`, `attested_at`, `statement` and `evidence` (`[{"path", "sha256"}]`, paths
relative to this directory). `entropytrade v1-gates` only reads them; agents must not create them.
