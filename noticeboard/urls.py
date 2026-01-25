from django.urls import path

from procurement.api import api

from . import views

urlpatterns = [
    path("api/", api.urls),
    path("", views.index),
]
