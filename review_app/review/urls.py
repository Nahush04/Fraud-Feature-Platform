from django.urls import path

from review import api, views

urlpatterns = [
    path("", views.queue, name="queue"),
    path("flags/<int:flag_id>/", views.transaction_detail, name="transaction_detail"),
    path("flags/<int:flag_id>/decide/", views.decide, name="decide"),
    path("api/flags/", api.ingest_flag, name="ingest_flag"),
]
