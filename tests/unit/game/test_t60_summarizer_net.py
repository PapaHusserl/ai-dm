# Т60 «Сеть» (docs/T60-PLAN.md п.1.4, 1.6, раздел 10): summarizer на границе при сетевых сбоях.
#   network -- мягкий сбой: primary -> backup (модель рассказчика) -> fallback-выжимка (тег
#   refusal_fallback), без меню; fatal по-прежнему меню. Primary с backup идёт на
#   retry.chain_delays ([] -- одна попытка), backup и primary без backup -- на полных delays.
from game_kit import end_scene_call, text_step, tools_step
from summarizer_kit import make_summ_rig, summ_fail_steps, summ_steps

NETWORK = [{"error": "transient", "message": "сеть"}] * 4
ERROR_MENU = ["retry", "switch_model", "save_and_quit"]
SONNET = "claude-sonnet-5-5"


def end_narrator(summary="Подсказка."):
    return [tools_step(end_scene_call(summary=summary)), text_step("Конец.")]


def scene(rig):
    return rig.runner.bundle.memory.scenes[0]


def test_primary_network_is_one_attempt_by_default(registry, cfg, tmp_path):
    narrator = end_narrator() + summ_steps("От рассказчика.")
    rig = make_summ_rig(registry, cfg, tmp_path, narrator, NETWORK)
    sleeps = []
    rig.runner.sleeper = sleeps.append
    rig.runner.play("ход")
    assert len(rig.summarizer_requests()) == 1
    assert sleeps == []


def test_primary_network_success_of_backup_gives_summarizer_source(registry, cfg, tmp_path):
    narrator = end_narrator() + summ_steps("От рассказчика.")
    rig = make_summ_rig(registry, cfg, tmp_path, narrator, NETWORK)
    rig.runner.play("ход")
    assert scene(rig).source == "summarizer"


def test_both_network_gives_fallback_summary_and_finished_boundary(registry, cfg, tmp_path):
    narrator = end_narrator() + NETWORK
    rig = make_summ_rig(registry, cfg, tmp_path, narrator, NETWORK)
    result = rig.runner.play("ход")
    assert result.boundary_failed is False
    assert result.menu is None
    assert rig.runner.failed_role is None
    assert rig.runner.bundle.session.boundary_pending is False
    assert scene(rig).source == "fallback"
    assert "refusal_fallback" in result.report_tags


def test_backup_after_network_of_primary_uses_full_delays(registry, cfg, tmp_path):
    narrator = end_narrator() + NETWORK
    rig = make_summ_rig(registry, cfg, tmp_path, narrator, NETWORK)
    sleeps = []
    rig.runner.sleeper = sleeps.append
    rig.runner.play("ход")
    assert len(rig.narrator_view().summarizer_requests()) == 4
    assert sleeps == [1, 3, 10]


def test_chain_delays_from_config_apply_to_primary_with_backup(registry, cfg, tmp_path):
    narrator = end_narrator() + summ_steps("От рассказчика.")
    rig = make_summ_rig(registry, cfg, tmp_path, narrator, NETWORK)
    rig.runner.app_cfg.retry.chain_delays = [2]
    sleeps = []
    rig.runner.sleeper = sleeps.append
    rig.runner.play("ход")
    assert len(rig.summarizer_requests()) == 2
    assert sleeps == [2]


def test_primary_without_backup_keeps_full_delays(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator() + NETWORK, [])
    rig.runner.summarizer_adapter = rig.narrator
    rig.runner.summarizer_model = rig.runner.model
    sleeps = []
    rig.runner.sleeper = sleeps.append
    result = rig.runner.play("ход")
    assert len(rig.narrator_view().summarizer_requests()) == 4
    assert sleeps == [1, 3, 10]
    assert result.boundary_failed is False
    assert scene(rig).source == "fallback"


def test_summarizer_session_with_backup_has_empty_primary_delays(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, [], [], summarizer_model=SONNET)
    session = rig.runner.new_summarizer_session()
    assert session.backup is not None
    assert session.policy.delays == []
    assert session.backup.policy is None


def test_summarizer_session_policy_keeps_the_rest_of_retry_config(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, [], [], summarizer_model=SONNET)
    rig.runner.app_cfg.retry.chain_delays = [5]
    rig.runner.app_cfg.retry.invalid_retries = 7
    policy = rig.runner.new_summarizer_session().policy
    assert policy.delays == [5]
    assert policy.invalid_retries == 7


def test_summarizer_session_without_backup_has_default_policy(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, [], [])
    rig.runner.summarizer_adapter = rig.narrator
    rig.runner.summarizer_model = rig.runner.model
    session = rig.runner.new_summarizer_session()
    assert session.backup is None
    assert session.policy is None


def test_config_retry_is_not_mutated_by_fast_policy(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, [], [], summarizer_model=SONNET)
    rig.runner.new_summarizer_session()
    assert rig.runner.app_cfg.retry.delays == [1, 3, 10]


def test_fatal_primary_still_gives_menu_and_skips_backup(registry, cfg, tmp_path):
    narrator = end_narrator() + summ_steps("От рассказчика.")
    rig = make_summ_rig(registry, cfg, tmp_path, narrator, summ_fail_steps())
    result = rig.runner.play("ход")
    assert result.boundary_failed is True
    assert result.menu == ERROR_MENU
    assert rig.runner.failed_role == "summarizer"
    assert rig.narrator_view().summarizer_requests() == []
