from django import template

from ..services import LABEL_IRRELEVANT, LABEL_NO, LABEL_YES

register = template.Library()

HOST_REPLIES = {
    LABEL_YES: ("그렇습니다.", "yes"),
    LABEL_NO: ("그렇지 않습니다.", "no"),
    LABEL_IRRELEVANT: ("관계없습니다.", "irrelevant"),
}
# Partial matches and vague questions both get the same short reply.
DEFAULT_REPLY = ("그럴 수도 있습니다.", "maybe")


@register.filter
def host_reply(label):
    """Short game-master reply shown to players for an internal judgement label."""
    return HOST_REPLIES.get(label, DEFAULT_REPLY)[0]


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
