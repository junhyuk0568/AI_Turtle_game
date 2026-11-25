from django.urls import path

from .account_views import delete_account_view, nickname_view, privacy_view
from .ranking_views import puzzle_ranking_view, ranking_view
from .views import (
    ask_question,
    home,
    play_view,
    report_judgement,
    result_view,
    start_game,
    submit_final_answer,
    use_hint,
)


app_name = "game"

urlpatterns = [
    path("", home, name="home"),
    path("me/nickname/", nickname_view, name="nickname"),
    path("me/delete/", delete_account_view, name="delete_account"),
    path("privacy/", privacy_view, name="privacy"),
    path("ranking/", ranking_view, name="ranking"),
    path("ranking/puzzle/<int:puzzle_id>/", puzzle_ranking_view, name="puzzle_ranking"),
    path("play/start/<int:puzzle_id>/", start_game, name="start_game"),
    path("play/<int:game_id>/", play_view, name="play"),
    path("play/<int:game_id>/ask/", ask_question, name="ask_question"),
    path("play/<int:game_id>/questions/<int:log_id>/report/", report_judgement, name="report_judgement"),
    path("play/<int:game_id>/hint/", use_hint, name="use_hint"),
    path("play/<int:game_id>/answer/", submit_final_answer, name="submit_final_answer"),
    path("play/<int:game_id>/result/", result_view, name="result"),
]
