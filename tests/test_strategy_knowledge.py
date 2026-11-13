from nexus.strategy_knowledge import (
    REGIMES, executable_strategy_ids, get_strategy, list_strategies,
    recommend_strategies,
)


def test_catalog_is_broad_and_contains_usage_and_regime_guidance():
    rows = list_strategies()
    assert len(rows) >= 40
    assert all(row["how_to_use"] and row["best_conditions"] and row["avoid_conditions"] for row in rows)
    assert all(row["required_data"] for row in rows)


def test_only_signal_engine_implemented_methods_are_executable():
    executable = executable_strategy_ids()
    assert len(executable) == 15
    assert all(get_strategy(strategy_id)["implemented"] for strategy_id in executable)
    assert all(not row["implemented"] for row in list_strategies() if row["status"] == "research_only")


def test_recommendations_do_not_promote_research_only_by_default():
    rows = recommend_strategies("sideways")
    assert rows
    assert all(row["implemented"] for row in rows)
    research = recommend_strategies("sideways", include_research=True)
    assert len(research) >= len(rows)


def test_catalog_returns_defensive_copies():
    first = get_strategy("ema_9_21")
    first["best_conditions"].append("fake")
    assert "fake" not in get_strategy("ema_9_21")["best_conditions"]


def test_unknown_regime_is_rejected():
    try:
        recommend_strategies("moon")
    except ValueError:
        pass
    else:
        raise AssertionError("Unknown regime was accepted")
