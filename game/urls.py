from django.urls import path

from .views import ask_question, home, play_view, result_view, start_game, submit_final_answer, use_hint


app_name = "game"

urlpatterns = [
    path("", home, name="home"),
    path("play/start/<int:puzzle_id>/", start_game, name="start_game"),
    path("play/<int:game_id>/", play_view, name="play"),
    path("play/<int:game_id>/ask/", ask_question, name="ask_question"),
    path("play/<int:game_id>/hint/", use_hint, name="use_hint"),
    path("play/<int:game_id>/answer/", submit_final_answer, name="submit_final_answer"),
    path("play/<int:game_id>/result/", result_view, name="result"),
]
