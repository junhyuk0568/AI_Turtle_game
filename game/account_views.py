from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import NicknameForm
from .models import GameSession, PlayerProfile

DELETE_CONFIRM_TEXT = "계정 삭제"


def _safe_next(request, fallback="game:home"):
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return target
    return fallback


@login_required(login_url="game:home")
def nickname_view(request):
    profile = PlayerProfile.objects.filter(user=request.user).first()
    if request.method == "POST":
        form = NicknameForm(request.POST, user=request.user)
        if form.is_valid():
            nickname = form.cleaned_data["nickname"]
            if profile:
                profile.nickname = nickname
                profile.save(update_fields=["nickname", "updated_at"])
            else:
                PlayerProfile.objects.create(user=request.user, nickname=nickname)
            messages.success(request, f"닉네임을 '{nickname}'(으)로 정했어요.")
            return redirect(_safe_next(request))
    else:
        form = NicknameForm(initial={"nickname": profile.nickname if profile else ""}, user=request.user)
    return render(
        request,
        "game/nickname.html",
        {"form": form, "is_new": profile is None, "next": request.GET.get("next", "")},
    )


@login_required(login_url="game:home")
def delete_account_view(request):
    if request.method == "POST":
        if request.POST.get("confirm", "").strip() != DELETE_CONFIRM_TEXT:
            messages.error(request, f"확인 문구 '{DELETE_CONFIRM_TEXT}'를 정확히 입력해 주세요.")
            return redirect("game:delete_account")
        user = request.user
        # Games point to users with SET_NULL; delete them explicitly so play records go too.
        GameSession.objects.filter(user=user).delete()
        logout(request)
        user.delete()
        messages.success(request, "계정과 플레이 기록을 삭제했어요.")
        return redirect("game:home")
    return render(request, "game/account_delete.html", {"confirm_text": DELETE_CONFIRM_TEXT})


def privacy_view(request):
    return render(request, "game/privacy.html")
