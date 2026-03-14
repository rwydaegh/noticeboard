from django.urls import path

from procurement.api import api

from . import views

urlpatterns = [
    path("api/", api.urls),
    path("", views.index),
    path("auth/csrf", views.csrf),
    path("auth/login", views.sign_in),
    path("auth/logout", views.sign_out),
    path("metrics", views.metrics),
]
