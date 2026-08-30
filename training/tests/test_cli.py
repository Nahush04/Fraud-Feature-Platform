import mlflow

import train.cli as cli


def test_run_command_prints_a_comparison_report(tmp_path, monkeypatch, synthetic_frame, capsys):
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path / 'mlflow.db'}")
    monkeypatch.setattr(cli, "load_training_frame", lambda delta_path: synthetic_frame)

    exit_code = cli.run(["run", "--delta-path", "unused", "--test-fraction", "0.2"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "train rows" in out
    assert "PR-AUC" in out
    assert "MLflow runs" in out
