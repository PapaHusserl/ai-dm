# Проверки качества (локально). Пороги: см. pyproject.toml и SMELLS_MAX ниже.
QLTY ?= $(HOME)/.qlty/bin/qlty
# ratchet: число запахов Qlty (сложность/параметры/дубли) на базовой линии; только вниз
SMELLS_MAX ?= 206
# мутации: MOD=ai_dm.rules.money (по умолчанию — модули, изменённые относительно HEAD)
MOD ?= $(shell git diff --name-only HEAD -- src/ai_dm | grep '\.py$$' | sed 's|^src/||; s|\.py$$||; s|/|.|g')

# мутации по функциям: FUNCS="ai_dm.ui.session:PlaySession.submit ai_dm.rules.money:to_cp"
# (модуль:функция или модуль:Класс.метод) -> шаблоны mutmut ai_dm.mod.x_func__mutmut_* и ai_dm.mod.xǁClassǁmethod__mutmut_*
# FUNCS задан -- MOD не используется
func_pattern = "$(word 1,$(subst :, ,$(1))).$(if $(findstring .,$(word 2,$(subst :, ,$(1)))),xǁ$(word 1,$(subst ., ,$(word 2,$(subst :, ,$(1)))))ǁ$(word 2,$(subst ., ,$(word 2,$(subst :, ,$(1))))),x_$(word 2,$(subst :, ,$(1))))__mutmut_*"
MUT_ARGS = $(if $(FUNCS),$(foreach f,$(FUNCS),$(call func_pattern,$(f))),$(foreach m,$(MOD),"$(m).*"))

.PHONY: quality lint smells cov dead sim-grid install-check linux-check mutate mutate-results

quality: lint smells dead cov

lint:
	$(QLTY) check --all --no-progress

smells:
	@n=$$($(QLTY) smells --all --no-snippets 2>/dev/null | grep -cE '^ +[0-9]+  '); \
	echo "qlty smells: $$n (max $(SMELLS_MAX))"; test $$n -le $(SMELLS_MAX)

cov:
	uv run pytest -q --cov --cov-report=term

dead:
	uv run vulture

# сетка sim_combat: класс x уровень x сцена, не хуже базовой линии - допуск (devtools/sim_grid_baseline.yaml)
sim-grid:
	uv run python -m ai_dm.devtools.sim_grid --check

install-check:
	uv run python devtools/check_install.py

linux-check:
	sh devtools/linux_check.sh

# segfault mutmut воспроизводится на широком TESTS (tests/unit/ui), forkserver не помогает (ломает фазу stats: _scproxy macOS в форке), гипотеза Textual не подтвердилась; правило: TESTS по узким файлам тестируемой функции, мутантов со статусом segfault перепроверять прогоном с тестами других файлов
# TESTS=пути -- гонять только эти тесты (фазы stats/clean и мутанты), иначе весь tests/ (~12 мин на фазу);
# pyproject.toml временно правится и восстанавливается; mutants/ пересоздаётся под выбор тестов
mutate:
	@test -n "$(MOD)$(FUNCS)" || { echo "нет изменённых модулей; укажи MOD=ai_dm.x.y"; exit 1; }
	@if [ -n "$(TESTS)" ]; then \
		rm -rf mutants; cp pyproject.toml .pyproject.mutmut.bak; \
		sel=$$(printf '"%s", ' $(TESTS) | sed 's/, $$//'); \
		sed -i.tmp "s|^pytest_add_cli_args_test_selection = .*|pytest_add_cli_args_test_selection = [$$sel]|" pyproject.toml; \
		rm -f pyproject.toml.tmp; \
		uv run mutmut run $(MUT_ARGS); rc=$$?; \
		mv .pyproject.mutmut.bak pyproject.toml; exit $$rc; \
	else uv run mutmut run $(MUT_ARGS); fi
	uv run mutmut results

mutate-results:
	uv run mutmut results
