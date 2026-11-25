import re

from django import forms

from .models import NICKNAME_PATTERN, RESERVED_NICKNAMES, PlayerProfile


class NicknameForm(forms.Form):
    nickname = forms.CharField(
        label="닉네임",
        max_length=12,
        help_text="2~12자, 한글·영문·숫자·밑줄(_)만 쓸 수 있어요. 순위표에 이 이름만 보여요.",
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_nickname(self):
        nickname = self.cleaned_data["nickname"].strip()
        if not re.fullmatch(NICKNAME_PATTERN, nickname):
            raise forms.ValidationError("2~12자의 한글, 영문, 숫자, 밑줄(_)만 쓸 수 있어요.")
        if nickname.lower() in RESERVED_NICKNAMES:
            raise forms.ValidationError("쓸 수 없는 닉네임이에요.")
        taken = PlayerProfile.objects.filter(nickname__iexact=nickname)
        if self.user is not None:
            taken = taken.exclude(user=self.user)
        if taken.exists():
            raise forms.ValidationError("이미 다른 사람이 쓰고 있는 닉네임이에요.")
        return nickname
