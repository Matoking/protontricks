from protontricks.config import get_config


def test_config(home_dir):
    """
    Test creating a configuration file, inserting a value into it and reading
    it back
    """
    config = get_config()

    config.set("General", "test_field", "test_value")

    # Ensure the configuration file now exists
    config_path = home_dir / ".config/protontricks/config.ini"
    assert config_path.exists()
    assert "test_value" in config_path.read_text()

    # Open the configuration file again, we should be able to read the value
    # back
    config = get_config()

    assert config.get("General", "test_field") == "test_value"


def test_config_default():
    """
    Test that a default value can be used if the field doesn't exist
    in the configuration file
    """
    config = get_config()

    assert config.get(
        "General", "fake_field", "default_value"
    ) == "default_value"

