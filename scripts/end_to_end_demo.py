"""End-to-end demo: a transaction scored by the real trained model, flagged,
notified into the review queue, and decided by an analyst -- all over real
HTTP between two real running servers (not Django's/Flask's test clients).

Requires: `data/feature_engineering_output` (a real Delta table -- see
feature_engineering/README.md) and `model/` (a real trained model -- see
training/README.md) to already exist. Run with the `serving` venv's Python
(it already has `requests`, `fakeredis`, and `fstore` installed):

    cd scripts
    ../serving/.venv/Scripts/python.exe end_to_end_demo.py

What it does, step by step (printed as it runs):
  1. Starts a real Django dev server (review_app), fresh sqlite db, one
     analyst user.
  2. Starts a real Flask dev server (serving), backed by the real trained
     model and the real IEEE-CIS feature history materialized into
     `fakeredis` (in-process -- no Docker/Redis needed for this demo; see
     docs/decisions.md).
  3. Searches the real materialized data for an (entity, amount) pair whose
     real model score actually clears the real decision threshold --
     doesn't fabricate a score.
  4. POSTs that transaction to the real /score endpoint. Asserts flagged
     and notified_review_queue are both true.
  5. Logs into the real Django server over real HTTP (session cookie +
     CSRF token), fetches the real queue page, confirms the transaction is
     there.
  6. Approves it via a real POST to /decide/, then fetches the transaction
     detail page and confirms the audit trail shows FLAGGED then APPROVED.
  7. Tears down both servers.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DJANGO_PORT = 8199
FLASK_PORT = 5099
DJANGO_URL = f"http://127.0.0.1:{DJANGO_PORT}"
FLASK_URL = f"http://127.0.0.1:{FLASK_PORT}"
ANALYST_USER = "demo_analyst"
ANALYST_PASSWORD = "demo-pass-not-for-prod"
API_KEY = "dev-local-key-change-me"


def step(msg: str) -> None:
    print(f"\n== {msg}")


def wait_for(url: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            requests.get(url, timeout=1)
            return
        except requests.RequestException:
            time.sleep(0.3)
    raise TimeoutError(f"{url} never came up")


def find_flagging_pair(model_dir: Path, delta_path: Path) -> tuple[str, float, float, float]:
    sys.path.insert(0, str(REPO_ROOT / "feature_store" / "src"))
    sys.path.insert(0, str(REPO_ROOT / "serving" / "src"))
    import fakeredis

    from fstore.offline import read_offline_features
    from fstore.online import RedisOnlineStore, materialize
    from serving.model import build_feature_row, load_model

    df = read_offline_features(str(delta_path))
    store = RedisOnlineStore(fakeredis.FakeStrictRedis())
    materialize(df, store)
    model, meta = load_model(str(model_dir))

    for card1 in df["card1"].value_counts().head(50).index.tolist():
        vector = store.read_vector(card1)
        for amount in (50, 500, 1500, 3000, 5000, 8000):
            row = build_feature_row(meta, amount, vector)
            score = float(model.predict_proba(row)[0][1])
            if score >= meta["decision_threshold"]:
                return str(card1), float(amount), score, meta["decision_threshold"]
    raise RuntimeError("no (entity, amount) pair among the top 50 entities clears the decision threshold")


def main() -> int:
    delta_path = REPO_ROOT / "data" / "feature_engineering_output"
    model_dir = REPO_ROOT / "model"
    if not delta_path.exists() or not model_dir.exists():
        print(f"missing {delta_path} or {model_dir} -- see feature_engineering/README.md and training/README.md")
        return 1

    review_app_dir = REPO_ROOT / "review_app"
    serving_dir = REPO_ROOT / "serving"
    review_py = review_app_dir / ".venv" / "Scripts" / "python.exe"
    serving_py = serving_dir / ".venv" / "Scripts" / "python.exe"

    step("Resetting review_app's sqlite db and creating the demo analyst user")
    db_path = review_app_dir / "db.sqlite3"
    db_path.unlink(missing_ok=True)
    env = {"DJANGO_USE_SQLITE": "true", "FLAG_INGEST_API_KEY": API_KEY}
    subprocess.run([str(review_py), "manage.py", "migrate"], cwd=review_app_dir, env={**_base_env(), **env}, check=True)
    subprocess.run(
        [
            str(review_py),
            "manage.py",
            "shell",
            "-c",
            f"from django.contrib.auth.models import User; "
            f"User.objects.filter(username='{ANALYST_USER}').delete(); "
            f"User.objects.create_user('{ANALYST_USER}', password='{ANALYST_PASSWORD}')",
        ],
        cwd=review_app_dir,
        env={**_base_env(), **env},
        check=True,
    )

    step(f"Starting the real Django review app on {DJANGO_URL}")
    django_proc = subprocess.Popen(
        [str(review_py), "manage.py", "runserver", f"127.0.0.1:{DJANGO_PORT}", "--noreload"],
        cwd=review_app_dir,
        env={**_base_env(), **env},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    wait_for(f"{DJANGO_URL}/login/")

    step("Finding a real (entity, amount) pair whose real model score clears the real decision threshold")
    card1, amount, expected_score, threshold = find_flagging_pair(model_dir, delta_path)
    print(f"   card1={card1} amount={amount} model_score={expected_score:.4f} threshold={threshold:.4f}")

    step(f"Starting the real Flask serving API on {FLASK_URL}")
    flask_script = f"""
import sys
sys.path.insert(0, r"{serving_dir / 'src'}")
sys.path.insert(0, r"{REPO_ROOT / 'feature_store' / 'src'}")
import fakeredis
from fstore.offline import read_offline_features
from fstore.online import RedisOnlineStore, materialize
from serving.app import create_app
from serving.model import load_model

df = read_offline_features(r"{delta_path}")
client = fakeredis.FakeStrictRedis()
materialize(df, RedisOnlineStore(client))
model, meta = load_model(r"{model_dir}")
app = create_app(redis_client=client, model=model, meta=meta)
app.run(host="127.0.0.1", port={FLASK_PORT})
"""
    flask_proc = subprocess.Popen(
        [str(serving_py), "-u", "-c", flask_script],
        env={**_base_env(), "REVIEW_APP_URL": DJANGO_URL, "FLAG_INGEST_API_KEY": API_KEY},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    wait_for(f"{FLASK_URL}/healthz")

    try:
        _run_demo(card1, amount, threshold)
    finally:
        step("Tearing down both servers")
        flask_proc.terminate()
        django_proc.terminate()
        flask_proc.wait(timeout=10)
        django_proc.wait(timeout=10)
        db_path.unlink(missing_ok=True)

    print("\nEND-TO-END DEMO PASSED")
    return 0


def _run_demo(card1: str, amount: float, threshold: float) -> None:
    step("POSTing the transaction to the real /score endpoint")
    resp = requests.post(
        f"{FLASK_URL}/score",
        json={"card1": card1, "TransactionAmt": amount, "transaction_id": "e2e-demo-txn"},
        timeout=5,
    )
    body = resp.json()
    print(f"   {body}")
    assert resp.status_code == 200
    assert body["flagged"] is True, f"expected the demo transaction to be flagged, got {body}"
    assert body["notified_review_queue"] is True, "expected the review queue to be notified"

    step("Logging into the real Django review app")
    session = requests.Session()
    login_page = session.get(f"{DJANGO_URL}/login/")
    csrf = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', login_page.text).group(1)
    login_resp = session.post(
        f"{DJANGO_URL}/login/",
        data={"username": ANALYST_USER, "password": ANALYST_PASSWORD, "csrfmiddlewaretoken": csrf},
        headers={"Referer": f"{DJANGO_URL}/login/"},
    )
    assert login_resp.status_code == 200 and "queue" in login_resp.url.lower() or login_resp.history

    step("Fetching the real review queue and confirming the transaction is there")
    queue_page = session.get(f"{DJANGO_URL}/")
    assert "e2e-demo-txn" in queue_page.text, "flagged transaction did not appear in the review queue"
    flag_id = re.search(r'href="/flags/(\d+)/"', queue_page.text).group(1)
    print(f"   found in queue as flag id {flag_id}")

    step("Approving it via a real POST to /decide/")
    detail_page = session.get(f"{DJANGO_URL}/flags/{flag_id}/")
    csrf = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', detail_page.text).group(1)
    session.post(
        f"{DJANGO_URL}/flags/{flag_id}/decide/",
        data={"decision": "approve", "note": "end-to-end demo", "csrfmiddlewaretoken": csrf},
        headers={"Referer": f"{DJANGO_URL}/flags/{flag_id}/"},
    )

    step("Confirming the audit trail shows FLAGGED then APPROVED")
    final_page = session.get(f"{DJANGO_URL}/flags/{flag_id}/").text
    assert "Approved" in final_page
    assert "Flagged" in final_page
    assert "end-to-end demo" in final_page
    print("   audit trail confirmed")


def _base_env() -> dict:
    import os

    return dict(os.environ)


if __name__ == "__main__":
    sys.exit(main())
