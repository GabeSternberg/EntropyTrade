# Local research interface

The buildless HTML/CSS/JavaScript workbench is served by `entropytrade-web` from
this checkout. It calls only the same-origin local API. No frontend package install,
external scripts, CDN, credential form, order endpoint or hosting service is used.
Formulation is template-only: documented signals or complete AND-only comparisons;
synthetic mode uses fixed mock proposals. Provider-backed research is a separate CLI flow.
Bitcoin authority mentions are shown separately from unresolved settlement sources.
Every result tab shows public acquisition completeness, HTTP receipt/contract/observation
counts and clocked failure summaries without expanding details. Downloaded text reports
include the same summary. Review completion and successful forward ingestion never imply
historical evaluation.

Run the dependency-free presentation regressions with
`node --test frontend/tests/acquisition.test.cjs` (Node 18+). They cover failed/partial
acquisition on all three tabs, literal source text and synthetic banners. Browser acceptance
is a separate requirement.

See [the workbench guide](../../docs/workbench.md) for operation, modes and limitations.
