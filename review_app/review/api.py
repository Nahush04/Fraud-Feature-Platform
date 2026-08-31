"""Machine-to-machine endpoint: serving/'s Flask API posts here when a
transaction's score clears its decision threshold. Not analyst-facing (see
views.py for the human UI), so it's API-key-gated rather than session-login-gated,
and CSRF-exempt since there's no browser session to carry a CSRF token.
"""

from __future__ import annotations

import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from review.services import create_flag

REQUIRED_FIELDS = ("transaction_id", "card1", "amount", "score", "threshold")


@csrf_exempt
@require_POST
def ingest_flag(request):
    api_key = request.headers.get("X-API-Key")
    if api_key != settings.FLAG_INGEST_API_KEY:
        return JsonResponse({"error": "unauthorized"}, status=401)

    try:
        payload = json.loads(request.body)
        missing = [f for f in REQUIRED_FIELDS if f not in payload]
        if missing:
            return JsonResponse({"error": f"missing fields: {missing}"}, status=400)

        flag = create_flag(
            transaction_id=payload["transaction_id"],
            card1=payload["card1"],
            amount=payload["amount"],
            score=payload["score"],
            threshold=payload["threshold"],
        )
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid JSON body"}, status=400)
    except (IntegrityError, ValidationError) as exc:
        # most likely: this transaction_id was already flagged once
        return JsonResponse({"error": str(exc)}, status=409)

    return JsonResponse({"flag_id": flag.id, "status": flag.status}, status=201)
