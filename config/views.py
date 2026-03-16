"""SPA catch-all view for serving the Vue frontend."""

from django.conf import settings
from django.http import HttpResponse

_index_html = None


def spa_view(request):
    """Serve the Vue SPA index.html for all non-API, non-admin routes."""
    global _index_html
    if _index_html is None:
        index_path = settings.BASE_DIR / "frontend" / "dist" / "index.html"
        _index_html = index_path.read_text()
    return HttpResponse(_index_html, content_type="text/html")
