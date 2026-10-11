# Подписи лога боя (A7, без латиницы): словари покрывают все значения Literal и кортежей движка.
from typing import get_args

from ai_dm.combat.actions.improvise import EFFECT_WORDS, EFFECTS
from ai_dm.combat.downed import INTENT_WORDS, INTENTS
from ai_dm.combat.end import OUTCOME_WORDS
from ai_dm.state.combat import Intent, Outcome


def test_outcome_words_cover_every_outcome():
    assert set(OUTCOME_WORDS) == set(get_args(Outcome))


def test_effect_words_cover_every_effect_except_prone():
    # «prone» берётся из названия состояния в реестре
    assert set(EFFECT_WORDS) == set(EFFECTS) - {"prone"}


def test_intent_words_cover_every_intent():
    assert set(INTENT_WORDS) == set(INTENTS) == set(get_args(Intent))


def test_words_are_russian():
    words = [*OUTCOME_WORDS.values(), *EFFECT_WORDS.values(), *INTENT_WORDS.values()]
    assert all(word.isascii() is False for word in words)
