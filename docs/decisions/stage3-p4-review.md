# Ревью П4 этапа 3 (мама-кабан): спецификация правок
Решения — оркестратор. K — src/**, docs/**; T — tests/**. Параллельно.
B1. Страж 4.1: смерть/уход NPC за кадром — `evidence_ref` должен быть броском этого же NPC (`actor_id == npc.id`, хранить actor в
    `add_roll`), иначе rejected `invalid-death`. Тест: бросок героя / чужого NPC → отказ, NPC жив.
B2. `then_ref` на verdict-кандидата — только после `world_verdict` с `holds=true` по нему, иначе Invalid `verdict_not_confirmed`;
    в world_rules.md «сначала world_verdict». Тест: npc_update до вердикта / по отклонённому → invalid, состояние без изменений.
D3. В режиме world `actor` у skill_check/saving_throw обязателен (`actor_required`); бросков героя за кадром нет.
D4. Без отдельного world-адаптера модель world = профиль провайдера рассказчика (`profiles[provider].world`); `/model narrator`
    при смене провайдера переключает и world на профиль нового провайдера; записать в notes.
D5. `then_ref` (необязательный) у `set_flag` и `world_notice` в режиме world; если указан на verdict — то же правило B2.
    Без `then_ref` — допустимо (свободные закадровые события), принятый риск записать.
D6. `apply_verdicts`: `next(..., None)` + пропуск, без StopIteration.
D7. Хроника из protocol — через общий помощник в `state/memory` (вынести из world_sim.add_entry), один путь записи.
M8–M11. Notes: кэш messages[0] у world — осознанно; комментарий про неиспользуемые параметры build; тест replay достройки после
    сбоя world (две world-записи, первая aborted); формулировка про отпечаток схемы.

## Наблюдение оркестратора после ревью
- CLI replay world: модель world берётся из текущего профиля, не из журнала (requested_model). При смене конфига между игрой и
  replay — расхождение отпечатка. Брать модель из записи журнала — в П5 (мелкая правка ui/cli).
