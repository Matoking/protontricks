from collections import namedtuple
from pathlib import Path

import vdf

import pytest
from protontricks.cli import main
from protontricks.steam import SteamApp


@pytest.fixture(scope="function", autouse=True)
def home_dir(monkeypatch, tmp_path):
    """
    Fake home directory
    """
    home_dir = tmp_path / "home" / "fakeuser"
    home_dir.mkdir(parents=True)

    monkeypatch.setenv("HOME", str(home_dir))

    yield home_dir


@pytest.fixture(scope="function", autouse=True)
def steam_dir(home_dir):
    """
    Fake Steam directory
    """
    steam_path = home_dir / ".steam"
    steam_path.mkdir()

    # Steam Runtime
    (steam_path / "root" / "ubuntu12_32").mkdir(parents=True)
    (steam_path / "root" / "compatibilitytools.d").mkdir(parents=True)

    (steam_path / "steam" / "appcache").mkdir(parents=True)
    (steam_path / "steam" / "config").mkdir(parents=True)
    (steam_path / "steam" / "steamapps").mkdir(parents=True)

    yield steam_path


@pytest.fixture(scope="function", autouse=True)
def steam_config_path(steam_dir):
    """
    Fake Steam config file at ~/.steam/steam/config/config.vdf
    """
    CONFIG_DEFAULT = {
        "InstallConfigStore": {
            "Software": {
                "Valve": {
                    "Steam": {
                        "ToolMapping": {}
                    }
                }
            }
        }
    }

    (steam_dir / "steam" / "config" / "config.vdf").write_text(
        vdf.dumps(CONFIG_DEFAULT)
    )

    yield steam_config_path


@pytest.fixture(scope="function", autouse=True)
def steam_libraryfolders_path(steam_dir):
    """
    Fake libraryfolders.vdf file at ~/.steam/steam/steamapps/libraryfolders.vdf
    """
    LIBRARYFOLDERS_DEFAULT = {
        "LibraryFolders": {
            # These fields are completely meaningless as far as Protontricks
            # is concerned
            "TimeNextStatsReport": "281946123974",
            "ContentStatsID": "23157498213759321679"
        }
    }

    (steam_dir / "steam" / "steamapps" / "libraryfolders.vdf").write_text(
        vdf.dumps(LIBRARYFOLDERS_DEFAULT)
    )


@pytest.fixture(scope="function")
def steam_app_factory(steam_dir):
    """
    Factory function to add fake Steam apps
    """
    def func(name, appid, library_dir=None, add_prefix=True):
        if not library_dir:
            steamapps_dir = steam_dir / "steam" / "steamapps"
        else:
            steamapps_dir = library_dir

        (steamapps_dir / "common" / name).mkdir(parents=True)

        (steamapps_dir / "appmanifest_{}.acf".format(appid)).write_text(
            vdf.dumps({
                "AppState": {
                    "appid": str(appid),
                    "name": name,
                    "installdir": name
                }
            })
        )

        if add_prefix:
            (steamapps_dir / "compatdata" / str(appid) / "pfx").mkdir(
                parents=True
            )
            (steamapps_dir / "compatdata" / str(appid) / "pfx.lock").touch()

        return SteamApp(
            name=name,
            appid=appid,
            install_path=str(steamapps_dir / "common" / name),
            prefix_path=str(
                steamapps_dir / "compatdata" / str(appid)
                / "pfx"
            )
        )

    return func


@pytest.fixture(scope="function")
def steam_library_factory(steam_dir, steam_libraryfolders_path, tmpdir):
    """
    Factory function to add fake Steam library folders
    """
    def func(name):
        library_dir = tmpdir / "mnt" / name
        library_dir.mkdir(parents=True)

        # Update libraryfolders.vdf with the new library folder
        libraryfolders_config = vdf.loads(
            steam_libraryfolders_path.read_text()
        )

        # Each new library adds a new entry into the config file with the
        # field name that starts from 1 and increases with each new library
        # folder.
        library_id = len(libraryfolders_config["LibraryFolders"].keys()) - 1
        libraryfolders_config[str(library_id)] = str(library_dir)

        libraryfolders_config.write_text(vdf.dumps(libraryfolders_config))

        return library_dir

    return func


class MockZenity:
    def __init__(self, args, mock_stdout):
        self.args = args
        self.mock_stdout = mock_stdout


class MockResult:
    def __init__(self, stdout):
        self.stdout = stdout


@pytest.fixture(scope="function", autouse=True)
def zenity(monkeypatch):
    """
    Monkeypatch the subprocess.run to store the args passed to the zenity
    command and to manipulate the output of the command
    """
    mock_zenity = MockZenity(args=[], mock_stdout="")

    def mock_subprocess_run(args, **kwargs):
        mock_zenity.args = args

        return MockResult(stdout=mock_zenity.mock_stdout.encode("utf-8"))

    monkeypatch.setattr(
        "protontricks.gui.subprocess.run",
        mock_subprocess_run
    )

    yield mock_zenity


@pytest.fixture(scope="function")
def cli(monkeypatch, capsys):
    """
    Run protontricks with the given arguments and environment variables
    and return the output
    """
    def func(args, env=None, include_stderr=False):
        if not env:
            env = {}

        with monkeypatch.context() as monkeypatch_ctx:
            # Monkeypatch environments values for the duration
            # of the CLI call
            for name, val in env.values():
                monkeypatch_ctx.setenv(name, val)

            main(args)

        stdout, stderr = capsys.readouterr()
        if include_stderr:
            return stdout, stderr
        else:
            return stdout

    return func
