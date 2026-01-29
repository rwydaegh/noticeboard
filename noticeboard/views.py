import json

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.http import FileResponse, JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_POST


@ensure_csrf_cookie
def index(request):
    path = settings.BASE_DIR / "frontend/dist/index.html"
    if not path.exists():
        return JsonResponse(
            {"detail": "Build the frontend with npm run build in frontend/. API: /api/docs"}
        )
    return FileResponse(path.open("rb"), content_type="text/html")


def csrf(request):
    return JsonResponse({"csrfToken": get_token(request)})


@require_POST
@csrf_protect
def sign_in(request):
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"detail": "Invalid JSON"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"detail": "Expected a JSON object"}, status=400)
    user = authenticate(
        request,
        username=str(payload.get("username", ""))[:150],
        password=str(payload.get("password", ""))[:1000],
    )
    if not user:
        return JsonResponse({"detail": "Username or password not recognized."}, status=401)
    login(request, user)
    return JsonResponse({"user": user.username, "csrfToken": get_token(request)})


@require_POST
@csrf_protect
def sign_out(request):
    logout(request)
    return JsonResponse({"user": None})
