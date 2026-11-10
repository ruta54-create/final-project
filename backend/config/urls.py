from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, HttpResponse
from django.urls import include, path, re_path
from django.views.static import serve


def frontend(request, path=""):
    """Serve the built React dashboard (frontend/dist).

    Real files (JS, CSS, logo) are returned as-is; every other URL such as
    /analytics or /control returns index.html so React Router can show the page.
    """
    dist = settings.FRONTEND_DIST
    if path and (dist / path).is_file():
        return serve(request, path, document_root=dist)
    index = dist / "index.html"
    if index.is_file():
        return FileResponse(open(index, "rb"), content_type="text/html")
    return HttpResponse(
        "<h2>Dashboard not built yet</h2><p>Run <code>cd frontend</code> then "
        "<code>npm run build</code>, and refresh this page.</p>",
        status=503,
    )


admin.site.site_header = "Edge-AI Smart Dustbin - Admin"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("bins.urls")),
    # photos from the ESP32-CAM (in production let Nginx serve this folder)
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    # everything that is not api/, admin/ or media/ -> React dashboard (must stay last)
    re_path(r"^(?!(?:api|admin|media)(?:/|$))(?P<path>.*)$", frontend),
]
