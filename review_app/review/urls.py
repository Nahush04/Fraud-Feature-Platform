from django.urls import path

from review import views

urlpatterns = [
    path("", views.queue, name="queue"),
    path("flags/<int:flag_id>/", views.transaction_detail, name="transaction_detail"),
    path("flags/<int:flag_id>/decide/", views.decide, name="decide"),
]
