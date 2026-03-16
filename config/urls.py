from django.contrib import admin
from django.urls import path
from ninja import NinjaAPI

from apps.accounts.api import router as accounts_router
from apps.audio.api import router as audio_router
from apps.player.api import router as player_router
from apps.stories.api import router as stories_router
from apps.stories.settings_api import router as settings_router

api = NinjaAPI(
    title="Voice In The Dark",
    version="2.0",
    description="Transform Reddit r/nosleep horror stories into dramatic audio productions.",
)

api.add_router("/auth/", accounts_router, tags=["Auth"])
api.add_router("/stories/", stories_router, tags=["Stories"])
api.add_router("/audio/", audio_router, tags=["Audio"])
api.add_router("/settings/", settings_router, tags=["Settings"])
api.add_router("/player/", player_router, tags=["Player"])

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
