import fakeredis

import fstore.cli as cli


def test_materialize_command(monkeypatch, delta_path, capsys):
    fake_client = fakeredis.FakeStrictRedis()
    monkeypatch.setattr(cli.redis.Redis, "from_url", classmethod(lambda cls, url: fake_client))

    exit_code = cli.run(["materialize", "--delta-path", delta_path])

    assert exit_code == 0
    assert "materialized 2 entities" in capsys.readouterr().out


def test_benchmark_command(monkeypatch, delta_path, capsys):
    fake_client = fakeredis.FakeStrictRedis()
    monkeypatch.setattr(cli.redis.Redis, "from_url", classmethod(lambda cls, url: fake_client))

    cli.run(["materialize", "--delta-path", delta_path])
    exit_code = cli.run(["benchmark", "--delta-path", delta_path, "--entity", "100", "--iterations", "5"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "online lookup" in out
    assert "speedup" in out
