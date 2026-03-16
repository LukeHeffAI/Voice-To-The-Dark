from django.contrib import admin
from django.urls import path, re_path
from django.views.generic import TemplateView
from ninja import NinjaAPI

from apps.accounts.api import router as auth_router
from apps.audio.api import router as audio_router
from apps.player.api import router as player_router
from apps.stories.api import router as stories_router
from apps.stories.api_settings import router as settings_router

api = NinjaAPI(
    title="Voice In The Dark",
    version="2.0",
    urls_namespace="api",
)

api.add_router("/auth/", auth_router)
api.add_router("/stories/", stories_router)
api.add_router("/audio/", audio_router)
api.add_router("/player/", player_router)
api.add_router("/settings/", settings_router)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    # SPA catch-all: serve Vue app for all non-API/admin routes
    re_path(r"^(?!api/|admin/).*$", TemplateView.as_view(template_name="index.html"), name="spa"),
]
