from sherpa.execution.simulation_paths import simulation_profile_slug


def test_slug_default() -> None:
    assert simulation_profile_slug("") == "default"
    assert simulation_profile_slug("  ") == "default"


def test_slug_sanitizes() -> None:
    assert simulation_profile_slug("lesson-1") == "lesson-1"
    assert simulation_profile_slug("a b@c#d") == "a_b_c_d"
