from django.urls import path

from procurement.api import api

urlpatterns = [
    path("api/", api.urls),
]
