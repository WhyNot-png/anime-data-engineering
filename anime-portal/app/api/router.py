"""Сборка всех роутеров API v1."""

from fastapi import APIRouter

from app.api import analytics, anime, dictionaries, users

api_router = APIRouter()
api_router.include_router(anime.router)
api_router.include_router(dictionaries.studios_router)
api_router.include_router(dictionaries.genres_router)
api_router.include_router(users.router)
api_router.include_router(analytics.router)
