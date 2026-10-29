# Executed history browser acceptance

`empty-*` files document an empty workspace and honest unsupported results.
`controlled-*` files document **CONTROLLED SOFTWARE EVIDENCE**. All populated market,
Coinbase and finalized outcome responses were created by the test-only fixture helper.
This label covers screenshots, downloads, traces, SQLite and copied run artifacts.
The existing adapter's `data_kind=real` and UI's REAL EVIDENCE banner identify its
receipt-processing path; the controlled fixture is not empirical evidence.

Both tests used Playwright-managed Chromium, a fresh context, an actual localhost
listener and the unmodified subprocess worker. Form submissions, all three result tabs,
both downloads and reopening completed history after restarting the server executed.
Each receipt lists four screenshots and four checksummed downloads; before/after bytes
match. JSON/JUnit results and traces retain the actual executed checks. The workspaces
were copied after shutdown, omitting transient SQLite/process locks.

These checks establish no successful live ingestion, historical accuracy, returns,
second-family empirical completion or V1 completion. Older October 28 browser denials
remain in their original bundle and are not rewritten as passes.
