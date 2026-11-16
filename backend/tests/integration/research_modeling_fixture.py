"""TEST-ONLY server: explicitly synthetic acquired-feature modeling through real jobs.

No production switch selects this fixture. Generation and dataset setup are controlled;
all immutable verification, model fitting, scoring, persistence and HTTP behavior are real.
There are no market books or certified fees and executable profitability remains refused.
"""

import argparse
from pathlib import Path
from typing import Any
from unittest.mock import patch

from entropytrade.api.server import WorkbenchServer
from entropytrade.domain.time import SimulatedClock
from entropytrade.execution.fee_evidence import FeeEvidenceStore
from entropytrade.research import modeling
from entropytrade.research.model import DataKind, HypothesisStatus, JobStatus, ResearchRequest
from entropytrade.research.service import ResearchService
from tests.research_modeling_support import MODEL_NOW, modeling_fixture


class SyntheticResearchService(ResearchService):
    with_execution = False

    def _generate(self, job: dict[str, Any], request: ResearchRequest) -> None:
        spec, _ = modeling_fixture(self.store.root)
        spec = spec.revalidated(
            objective=request.objective, rules=() if self.with_execution else spec.rules
        )
        self.store.save_hypotheses(
            job["id"], [(spec, HypothesisStatus.PROPOSED, (), "")], now=self.now()
        )
        self.store.transition(
            job["id"],
            JobStatus.PLANNING,
            "CONTROLLED SYNTHETIC hypothesis recorded; no provider called",
            now=self.now(),
        )

    def _featurize(self, job: dict[str, Any], request: ResearchRequest) -> None:
        spec, artifacts = modeling_fixture(self.store.root)
        for artifact in artifacts:
            self.store.register_feature(job["id"], artifact, [spec.hypothesis_id], now=self.now())
        if self.with_execution:
            from tests.research_execution_support import execution_fixture

            dataset_id, fees = execution_fixture(self.store.root, spec, artifacts)
            for fee in fees:
                FeeEvidenceStore(self.workspace).put(fee)
            acquisition_id = self.store.plan_acquisition(
                "controlled-execution:" + dataset_id,
                "controlled-execution",
                {
                    "entity": "CLIPHL",
                    "series": "KXHIGHPHIL",
                    "start": artifacts[0]["window"][0],
                    "end": artifacts[0]["window"][1],
                },
                status="queued",
                now=self.now(),
            )
            self.store.finish_acquisition(
                acquisition_id,
                "completed",
                "CONTROLLED SYNTHETIC market evidence fixture; no network calls",
                dataset_id=dataset_id,
                now=self.now(),
            )
            quotes = next(
                r for r in self.store.requirements(job["id"]) if r.kind is DataKind.DECISION_QUOTES
            )
            self.store.link_acquisition(
                job["id"], acquisition_id, quotes.requirement_id, "controlled-test-setup"
            )
        super()._featurize(job, request)


def main() -> None:
    parser = argparse.ArgumentParser(description="TEST-ONLY synthetic research modeling server")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--with-execution", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    server = WorkbenchServer(repo, args.workspace, port=args.port)
    service = SyntheticResearchService(
        server.jobs.root,
        repo,
        clock=SimulatedClock(MODEL_NOW),
        transport_label="controlled_synthetic",
        lease_fd=server.lock.fileno(),
        poll_seconds=0.1,
    )
    service.with_execution = args.with_execution
    server.research = service
    actual_plan, actual_run = modeling.plan_hypothesis, modeling.run_hypothesis
    actual_verify = modeling.verify_hypothesis

    def plan(**kwargs: Any) -> dict[str, Any]:
        return actual_plan(**(kwargs | {"data_kind": "synthetic"}))

    def run(**kwargs: Any) -> dict[str, Any]:
        return actual_run(**(kwargs | {"data_kind": "synthetic"}))

    def verify(**kwargs: Any) -> dict[str, Any]:
        return actual_verify(**(kwargs | {"data_kind": "synthetic"}))

    with (
        patch.object(modeling, "verify_hypothesis", side_effect=verify),
        patch.object(modeling, "plan_hypothesis", side_effect=plan),
        patch.object(modeling, "run_hypothesis", side_effect=run),
    ):
        server.research.start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
