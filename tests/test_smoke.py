def test_config_loads():
    from infra.config import load_yaml

    assert isinstance(load_yaml("optimizer.yaml"), dict)
