from django import template

from ..services import FINAL_ANSWER_CORRECT, FINAL_ANSWER_INSUFFICIENT, LABEL_IRRELEVANT, LABEL_NO, LABEL_YES

register = template.Library()

# The host speaks in short plain sentences, as the play page promises.
HOST_REPLIES = {
    LABEL_YES: ("그렇다.", "yes"),
    LABEL_NO: ("아니다.", "no"),
    LABEL_IRRELEVANT: ("관계없다.", "irrelevant"),
}
# Partial matches and vague questions both get the same short reply.
DEFAULT_REPLY = ("그럴 수도.", "maybe")

FINAL_VERDICTS = {
    FINAL_ANSWER_CORRECT: "정답이다.",
    FINAL_ANSWER_INSUFFICIENT: "아직 부족하다.",
}


@register.filter
def host_reply(label):
    """Short game-master reply shown to players for an internal judgement label."""
    return HOST_REPLIES.get(label, DEFAULT_REPLY)[0]


@register.filter
def host_verdict(label):
    """Host's short line for a final-answer judgement label."""
    return FINAL_VERDICTS.get(label, label)


@register.filter
def reply_class(label):
    return HOST_REPLIES.get(label, DEFAULT_REPLY)[1]


@register.filter
def play_time(seconds):
    """Clear time for rankings, e.g. 75 -> "1분 15초"."""
    if seconds is None:
        return "-"
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}시간 {minutes}분"
    if minutes:
        return f"{minutes}분 {secs}초"
    return f"{secs}초"
