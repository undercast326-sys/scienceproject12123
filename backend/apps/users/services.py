from .models import UserProfile

XP_PER_CORRECT_ANSWER = 10
XP_PER_LEVEL = 100


def lock_profile(user):
    """Return the user's profile row locked for the rest of the current transaction.

    Finishing a quiz or mock test locks it first, so two finishes by the same user
    run one after another and can't both treat a question as answered for the first time.
    """
    UserProfile.objects.get_or_create(user=user)
    return UserProfile.objects.select_for_update().get(user=user)


def credit_result(profile, total, correct, xp_correct):
    """Add a finished test's numbers to a profile locked with lock_profile().

    Stats count every answer; XP is granted only for `xp_correct` answers —
    questions the user got right for the first time — so replaying the same
    questions can't farm levels.
    """
    xp_gained = xp_correct * XP_PER_CORRECT_ANSWER
    profile.solved += total
    profile.correct += correct
    profile.wrong += total - correct
    profile.xp += xp_gained
    profile.level = profile.xp // XP_PER_LEVEL + 1
    profile.save(update_fields=['solved', 'correct', 'wrong', 'xp', 'level'])
    return xp_gained
