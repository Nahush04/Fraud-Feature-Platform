from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from review.models import Flag
from review.services import decide_flag


@login_required
def queue(request):
    flags = Flag.objects.filter(status=Flag.Status.PENDING).select_related("transaction").order_by("-transaction__score")
    return render(request, "review/queue.html", {"flags": flags})


@login_required
def transaction_detail(request, flag_id: int):
    flag = get_object_or_404(Flag.objects.select_related("transaction"), pk=flag_id)
    audit_entries = flag.audit_entries.select_related("actor").all()
    return render(request, "review/transaction_detail.html", {"flag": flag, "audit_entries": audit_entries})


@login_required
@require_POST
def decide(request, flag_id: int):
    flag = get_object_or_404(Flag, pk=flag_id)
    approve = request.POST.get("decision") == "approve"
    note = request.POST.get("note", "")
    decide_flag(flag, approve=approve, actor=request.user, note=note)
    return redirect("queue")
