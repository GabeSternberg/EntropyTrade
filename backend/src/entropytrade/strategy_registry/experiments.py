"""Write registry rows to a local MLflow directory. Money stays a string.

MLflow metrics are floats. Equity is logged as a parameter so it is not coerced
through a float. No tracking server is started.
"""

from pathlib import Path

from entropytrade.strategy_registry.store import Registry


def log_rows(registry: Registry, tracking_dir: Path) -> str:
    """Create or reuse the ``entropytrade`` experiment and return its id."""
    import mlflow

    tracking_dir.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(tracking_dir.resolve().as_uri())
    experiment = mlflow.set_experiment("entropytrade")
    for row in registry.rows():
        with mlflow.start_run(run_name=row.strategy_id):
            mlflow.log_param("strategy_id", row.strategy_id)
            mlflow.log_param("spec_hash", _clip(row.spec_hash))
            mlflow.log_param("state", row.state)
            mlflow.log_param("verdict", row.verdict)
            mlflow.log_param("ending_equity", row.ending_equity or "none")
            mlflow.log_param("digest", _clip(row.digest or "none"))
            mlflow.log_param("hypothesis", _clip(row.hypothesis))
    experiment_id = experiment.experiment_id
    if not isinstance(experiment_id, str):
        raise TypeError("MLflow experiment id was not a string")
    return experiment_id


def _clip(value: str) -> str:
    return value if len(value) <= 500 else value[:500]
