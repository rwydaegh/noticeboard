from django.conf import settings
from django.http import FileResponse, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie


@ensure_csrf_cookie
def index(request):
    path = settings.BASE_DIR / "frontend/dist/index.html"
    if not path.exists():
        return JsonResponse(
            {"detail": "Build the frontend with npm run build in frontend/. API: /api/docs"}
        )
    return FileResponse(path.open("rb"), content_type="text/html")
