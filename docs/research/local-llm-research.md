# Локальная нейросеть vs Gemini/Anthropic — ресёрч дяди-кабана (2026-10-12)

Вопрос проектировщика: поднять локальную модель — варианты, цена, сравнение с Gemini/Anthropic — для игры (API-токены) и
для разработки (подписка Claude). Готов купить отдельное железо. Приоритеты (ответ 2026-10-12): цена, отсутствие
цензуры, возможность расшарить модель близким. Тариф — Claude Max 5x ($100/мес), иногда упирается в лимит.

**Качество данных:** цены — агрегаторы и блоги (официальные страницы Google/Anthropic не открывались); скорости на Mac —
отчёты пользователей, не замеры; бенчмарки — в основном от вендоров; цены в УЗ/РФ и тарифы электричества не проверены.

## 1. Фактический расход игры (saves/*/meta/costs.jsonl, 04–12.10.2026)

| Роль / модель | Вызовов | Ср. вход (вкл. кэш) | Ср. выход | $ |
|---|---|---|---|---|
| narrator gemini-3.8-flash | 1139 | ~17,8 тыс. | ~633 | 10,27 |
| world gemini-3.5-flash-lite | 90 | ~7,5 тыс. | ~75 | 0,17 |
| summarizer gemini-3.5-flash-lite | 76 | ~5,6 тыс. | ~148 | 0,14 |
| narrator claude-sonnet-5-5 | 78 | ~19,6 тыс. | ~297 | 1,37 |
| haiku-4-5 (world/summarizer) | 10 | — | — | 0,10 |
| **Итого** | | | | **≈ $12,1 за 8 дней** (с копиями сейвов — чуть завышено) |

Ход рассказчика: Gemini ≈ $0,009, Sonnet ≈ $0,018. ≈ $1,5/день (пик $4), ≈ $35–50/мес при таком темпе (в основном тестовые
прогоны); просто игра пару часов в неделю — ≈ $5–10/мес. Цены конфига: 3.8-flash $0,75/$3,75 за 1 млн (с 2027-01-01 —
$1,50/$7,50), flash-lite $0,30/$2,50.

## 2. Цены моделей ($ за 1 млн, вход/выход)

| Вариант | Цена | Заметки |
|---|---|---|
| Gemini 3.8 Flash | 0,75 / 3,75 (2027 — 1,50 / 7,50) | хороший русский, бывают refusal |
| Claude Haiku 4.5 / Sonnet 5.5 / Opus 5.5 | 1/5, 2/10, 4/20 | чтение кэша — 10 % |
| DeepSeek V3.2 (OpenRouter) | 0,21 / 0,32 | tool use есть, русский — проверить |
| Qwen3.6-35B-A3B | 0,14 / 1,00 | |
| GLM-5.1 / Kimi K2.6 | ~1,05 / 3,5 и ~0,75 / 3,5 | |
| DeepSeek V4 Pro (DeepInfra) | 1,30 / 2,60 | |

Подписки Claude: Pro $20, Max 5x $100, Max 20x $200 (лимит раз в 5 ч). OpenRouter — +5,5 % при пополнении; модерация у
части провайдеров — не проверено. Подписки Google AI — не проверены.

## 3. Текущий MacBook Air M1 16 ГБ

Модели 7–14B Q4 (Ollama / LM Studio / MLX): Qwen3 8B/14B, Gemma 12B, YankaGPT-8B (русская ролевая проза); Mistral Small
24B — впритык. ~10–20 ток/с, длинный вход (8–18 тыс./ход) — десятки секунд; проза и tool use заметно хуже Flash; ниже
4 бит tool calling ломается. **Для эксперимента — бесплатно, для игры — нет.**

## 4. Железо (цены США; в УЗ/РФ +15–30 %, не проверено; 2026 — дефицит памяти, Apple подняла цены 25.06.2026)

| Конфигурация | Цена | Что тянет | Скорость | Эл-во/мес |
|---|---|---|---|---|
| Mac mini M5 Pro 64 ГБ | от $1 699 (база; 64 ГБ дороже) | MoE до ~80B, dense 27–32B | 35B-A3B — десятки ток/с; 32B ~10–15 | $1–3 |
| Ryzen AI Max+ 395 128 ГБ (HP Z2 Mini G1a и др.) | ≈ половина DGX Spark (не найдено) | gpt-oss-120b, MoE 100–120B | ~34 ток/с, префилл ~340 ток/с | $2–4 |
| NVIDIA DGX Spark 128 ГБ | $4 699 прайс, в рознице $7–9 тыс. | как Ryzen + CUDA | ~38 ток/с, префилл ~1 700 | $2–4 |
| Mac Studio M5 Max 128 ГБ | ~$5 099–5 399 | Qwen3.5-122B-A10B, gpt-oss-120b | ~18–25 ток/с (замер M3 Max) | $2–4 |
| ПК с RTX 5090 32 ГБ | карта $3 500–4 500 + ~$1 500 | dense до ~32B | самый быстрый в классе | $5–15 |
| Mac Studio M5 Ultra 512 ГБ | нет цены (конец октября), база от $5 499 | GLM-5.x, DeepSeek-класс | замеров нет | $3–6 |

Окупаемость против API игры ($10–50/мес): Mac mini — 3–14 лет, Mac Studio — 8–40 лет. Против Max $200 Mac Studio
окупился бы за ~2 года, но Claude Code не заменяет.

**Минимум «для игры»:** Mac mini 64 ГБ или Ryzen AI Max 128 ГБ; русский «как Flash» не гарантирован.
**«Уровень Claude Code» локально недостижим за разумные деньги:** лучшим open-weight кодерам (DeepSeek V4 Pro, GLM-5.x,
Kimi K2.7) нужно ≥ 512 ГБ; на 128 ГБ — Qwen3.6-27B / Qwen3-Coder-Next («хороший помощник», медленный длинный контекст).

## 5. Аренда GPU

RTX 4090 ~$0,34–0,69/ч, H100 ~$0,9–3/ч. Для одного игрока невыгодно (2 ч на H100 ≈ $4 против ≈ $1,5 игрового дня на
Gemini); проще OpenRouter.

## 6. Вывод дяди-кабана

- Игра: основной — Gemini Flash; запасной при refusal — open-weight через OpenRouter (DeepSeek V3.2/Qwen); сначала
  бесплатно погонять Qwen3 14B / YankaGPT-8B на M1. Железо по деньгам не окупается; оправдано приватностью/без цензуры.
- Разработка: остаться на подписке Claude; промежуточно — GLM/Kimi по API в OpenCode (не проверено на конвейере).
- Риски: русская проза у моделей < 30B; tool use/JSON на квантованных; префилл на Mac; цены завышены; бенчмарки вендоров.
- Строительный блок в проекте: OpenAI-совместимый API (llama.cpp/Ollama/MLX/vLLM) → один новый адаптер (решение папы-кабана).

## 7. Вывод оркестратора с учётом приоритетов проектировщика

- Разработка — остаться на Max 5x; при упоре в лимит дешевле Max 20x (+$100/мес), чем железо.
- «Своя модель без цензуры для близких» — то, что API не даёт: abliterated/uncensored версии open-weight (напр. Qwen),
  Ollama + Open WebUI (аккаунты), доступ через Tailscale. Mac/Ryzen обслуживают запросы по очереди (2–4 человека — терпимо);
  для одновременной работы — NVIDIA + vLLM.
- Путь: (1) бесплатно M1 + Ollama + Open WebUI, uncensored Qwen3 14B на русском и своих сценах; (2) если устроит — брать
  128 ГБ, не 64: Ryzen AI Max+ 395 (дешевле) или Mac Studio M5 Max (~$5,1–5,4 тыс.); (3) с покупкой подождать 1–3 мес.
  (дефицит памяти, выход M5 Ultra в конце октября).
- Запасной рассказчик через свой сервер/OpenRouter — кандидат в Р2.

## Источники
morphllm.com/gemini-api-pricing; anotherwrapper.com (Gemini 3.7 Flash, Qwen/DeepSeek); finout.io и chudi.dev (Claude
pricing); openrouter.ai/compare; betonai.net (OpenRouter 2026); morphllm.com/openrouter-alternative; spheron.network
(RunPod vs Vast); intuitionlabs.ai (H100); vast.ai/blog; iclarified.com (Mac 2026); openclawdc.com (Mac Studio);
pinggy.io (hardware for coding agents); medium.com/@nithin_94885 (local LLM for coding 2026); tiny.write.as/iain-harper
(«A $10k Mac Studio won't replace your API bill»); promptquorum.com (creative writing 2026); siliconflow.com (Russian LLM);
promptlayer.com (YankaGPT 8B); forums.developer.nvidia.com (DGX Spark $4 699); monoist.itmedia.co.jp; falcao.org и
starryhope.com (Spark vs AI Max); aiindigo.com (Mac Studio M5 Max 128 ГБ); tech-insider.org (GPU prices 2026);
how2shout.com (рост цен Apple); fungies.io (open-source LLMs 2026); guru3d.com (RTX 5090 EU); insiderllm.com.

Расход: dyadya-kaban ~53+58 тыс. ток.
