from django.urls import path

from .views import ask_question, home, play_view, start_game, use_hint


app_name = "game"

urlpatterns = [
    path("", home, name="home"),
    path("play/start/<int:puzzle_id>/", start_game, name="start_game"),
    path("play/<int:game_id>/", play_view, name="play"),
    path("play/<int:game_id>/ask/", ask_question, name="ask_question"),
    path("play/<int:game_id>/hint/", use_hint, name="use_hint"),
]
