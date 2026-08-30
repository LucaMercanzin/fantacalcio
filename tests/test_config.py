"""TASK-019/A4: config.py is the single source of truth for league rules —
these lock in that the modules which used to redefine ROLE_SLOTS/
TOTAL_CREDITS locally now all agree with it (and with each other)."""

import config
from ranking import budget, lp_optimizer


def test_role_slots_sums_to_a_full_squad():
    assert sum(config.ROLE_SLOTS.values()) == 25


def test_budget_module_reexports_config_role_slots():
    assert budget.ROLE_SLOTS is config.ROLE_SLOTS


def test_lp_optimizer_reexports_config_role_slots():
    assert lp_optimizer.ROLE_SLOTS is config.ROLE_SLOTS


def test_default_formation_has_eleven_starters():
    from ranking.ideal_squad import FORMATIONS
    assert sum(FORMATIONS[config.DEFAULT_FORMATION].values()) == 11
