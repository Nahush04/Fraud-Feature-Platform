# review_app

Django + MySQL analyst review queue: transactions `serving/`'s Flask API
flags as high-risk land here for a human decision, with an append-only audit
trail.

## Why a human-in-the-loop review queue

A fraud model's score isn't a verdict — a false positive that auto-blocks a
legitimate transaction is its own cost. Flagged transactions wait in a
queue; an analyst approves or rejects, and every decision (and the original
flag) is recorded in `AuditLogEntry`, which is append-only by construction
(`AuditLogEntry.delete()` raises `NotImplementedError` — enforced at the
model layer, not just by convention, and blocked in the Django admin too).
Same governance pattern as the audit trail in the GenieChat/Help Center
portfolio entries.

## Install

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Database

MySQL is the real, intended backend, via PyMySQL (pure Python -- no
mysqlclient C-extension build toolchain needed) rather than a live MySQL
server on this dev machine right now:

```bash
docker compose -f ../infra/docker-compose.yml up -d mysql
export DJANGO_USE_SQLITE=false
export MYSQL_HOST=localhost MYSQL_DATABASE=fraud_review MYSQL_USER=fraud_app MYSQL_PASSWORD=fraud_app_local_only
```

Without Docker, `DJANGO_USE_SQLITE=true` (the default) runs against sqlite —
every model/migration/query here is plain Django ORM, so it's unchanged
either way. See `docs/decisions.md` for why.

## Run

```bash
python manage.py migrate
python manage.py createsuperuser   # or shell: User.objects.create_user(...)
python manage.py runserver
```

`/` is the review queue (login required); `/flags/<id>/` is a transaction's
detail + audit trail + approve/reject form; `/admin/` is Django admin
(models registered, `AuditLogEntry` delete disabled there too).

## Feeding real flags in

```python
from review.services import create_flag
create_flag(transaction_id="txn-123", card1="7919", amount="125.50", score=0.91, threshold=0.75)
```

This is the exact function the M7 integration point calls when `serving/`'s
`/score` endpoint returns `flagged: true` — see `docs/architecture.md`.

## Layout

```
fraud_review/    Django project config (settings, urls) -- MySQL by default,
                 documented sqlite fallback for local dev/tests
review/
  models.py       Transaction, Flag, AuditLogEntry (append-only)
  services.py     create_flag / decide_flag -- callable from a script or a view
  views.py        queue (login required), transaction_detail, decide (POST only)
  admin.py         all three models registered; AuditLogEntry delete disabled
  templates/review/
  tests/           Django TestCase suite: models, services, views (incl.
                    the append-only guarantee and the anonymous-user-blocked case)
```

## Tests

```bash
python manage.py test review
```

15 tests, run against sqlite (see Database above) — all pass, and the whole
login -> queue -> approve -> audit-trail flow was additionally verified
against a real running dev server over real HTTP (`docs/decisions.md`).
