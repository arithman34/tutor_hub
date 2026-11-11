import json
from datetime import datetime, timezone
from urllib.parse import quote

from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .auth import login_required
from .data_transfer import build_user_export, import_user_data


@login_required
def data_page(request):
    return render(request, "data/index.html", {"user": request.user, "active_page": "data"})


@login_required
def data_export(request):
    data = build_user_export(request.user)
    filename = f"tutorhub_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    response = HttpResponse(json.dumps(data, indent=2), content_type="application/json")
    response["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@login_required
@require_http_methods(["POST"])
def data_import(request):
    file = request.FILES.get("file")
    if file is None:
        return redirect("/data?error=" + quote("Choose a file to import"))
    try:
        import_user_data(request.user, json.loads(file.read()))
    except Exception as exc:
        return redirect(f"/data?error={quote(str(exc) or type(exc).__name__)}")
    return redirect("/data?imported=1")
