"""SPA catch-all view for serving the Vue frontend."""

import logging

from django.conf import settings
from django.http import HttpResponse

logger = logging.getLogger(__name__)

_index_html = None


def spa_view(request):
    """Serve the Vue SPA index.html for all non-API, non-admin routes."""
    global _index_html
    if _index_html is None:
        index_path = settings.BASE_DIR / "frontend" / "dist" / "index.html"
        try:
            _index_html = index_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.error("SPA index.html not found at %s", index_path)
            return HttpResponse(
                "Frontend not built. Run 'npm run build' in the frontend directory.",
                content_type="text/plain",
                status=503,
            )
    return HttpResponse(_index_html, content_type="text/html")
