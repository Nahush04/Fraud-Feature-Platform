import json

import mlflow

import train.cli as cli
from train.data import FEATURE_COLUMNS


def test_run_command_prints_a_comparison_report(tmp_path, monkeypatch, synthetic_frame, capsys):
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path / 'mlflow.db'}")
    monkeypatch.setattr(cli, "load_training_frame", lambda delta_path: synthetic_frame)

    exit_code = cli.run(["run", "--delta-path", "unused", "--test-fraction", "0.2"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "train rows" in out
    assert "PR-AUC" in out
    assert "MLflow runs" in out


def test_run_command_saves_model_and_metadata_when_model_dir_given(tmp_path, monkeypatch, synthetic_frame):
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path / 'mlflow.db'}")
    monkeypatch.setattr(cli, "load_training_frame", lambda delta_path: synthetic_frame)
    model_dir = tmp_path / "model"

    exit_code = cli.run(["run", "--delta-path", "unused", "--model-dir", str(model_dir)])

    assert exit_code == 0
    assert (model_dir / "model.json").exists()
    meta = json.loads((model_dir / "meta.json").read_text())
    assert meta["feature_columns"] == FEATURE_COLUMNS
    assert 0 <= meta["decision_threshold"] <= 1
