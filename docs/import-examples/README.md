# Примеры выжимок для `--import` (живой прогон Б3)

| Файл | Что будет |
|---|---|
| `valid.txt` | Импорт проходит: 4 локации, 3 именованных NPC + безымянные стражники, 2 фракции, 1 богиня, тайны и тон. Код 0. |
| `invalid-empty.txt` | Пустой файл → «Выжимка пуста.», код 1, модель не вызывается. |
| `invalid-blank.txt` | Только пробелы и переводы строк → «Выжимка пуста.», код 1. |
| `invalid-too-long.txt` (в репо нет, создать: `python -c "print('x'*60001)" > /tmp/too-long.txt`) | Больше 60000 символов (`[import] max_chars`) → «Выжимка длиннее 60000 символов (…)», код 1. |
| `invalid-cp1251.txt` | Не UTF-8 → «Выжимка не прочитана: …», код 1. |

Невалидные отсекаются до вызова модели — бесплатно.

```
uv run ai-dm --import docs/import-examples/valid.txt --campaign grey_harbor
uv run ai-dm --import docs/import-examples/invalid-empty.txt --campaign x
```
