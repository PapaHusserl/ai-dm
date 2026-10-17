import json
import sys

from ai_dm.campaign.loader import CAMPAIGNS_DIR, pack_content_dir, pack_monster_scope
from ai_dm.config.app import load_settings
from ai_dm.content.loader import load_registry
from ai_dm.master.context import estimate_tokens
from ai_dm.master.prompt import PromptBuilder
from ai_dm.protocol.schema import MODE_TOOLS

PACKS = ("dusk_academy", "drunk_dragon")


def main(argv=None):
    app = load_settings().app
    cpt = app.master.chars_per_token
    builder = PromptBuilder(app)
    print("static tokens (правила + схемы инструментов, общий chars_per_token):")
    for mode in sorted(MODE_TOOLS):
        tokens = builder.static_tokens(mode)
        print(f"  {mode:<18} rules {tokens['rules']:>6}  tools {tokens['tools']:>6}  "
              f"total {tokens['total']:>6}")
    print("monster_ids в system[1] (токены, список целиком -> список пака):")
    for pack in PACKS:
        # как ui.cli.campaign_registry: devtools не импортирует ui (test_architecture)
        pack_dir = CAMPAIGNS_DIR / pack
        content_dir = pack_content_dir(pack_dir)
        registry = load_registry([content_dir] if content_dir is not None else [])
        registry.monster_scope = pack_monster_scope(pack_dir)
        full = estimate_tokens(json.dumps(registry.ids("monster")), cpt)
        scoped = estimate_tokens(json.dumps(registry.narrator_monster_ids()), cpt)
        print(f"  {pack:<14} {full:>6} -> {scoped:>6}  (-{full - scoped})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
