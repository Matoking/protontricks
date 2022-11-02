import pytest

from pathlib import Path

from protontricks.flatpak import (get_inaccessible_paths,
                                  get_running_flatpak_version)


class TestGetRunningFlatpakVersion:
    def test_flatpak_not_active(self):
        """
        Test Flatpak version detection when Flatpak is not active
        """
        assert get_running_flatpak_version() is None

    def test_flatpak_active(self, monkeypatch, tmp_path):
        """
        Test Flatpak version detection when Flatpak is active
        """
        flatpak_info_path = tmp_path / "flatpak-info"

        flatpak_info_path.write_text(
            "[Application]\n"
            "name=fake.flatpak.Protontricks\n"
            "\n"
            "[Instance]\n"
            "flatpak-version=1.12.1"
        )
        monkeypatch.setattr(
            "protontricks.flatpak.FLATPAK_INFO_PATH", str(flatpak_info_path)
        )

        assert get_running_flatpak_version() == (1, 12, 1)


class TestGetInaccessiblePaths:
    def test_flatpak_disabled(self):
        """
        Test that an empty list is returned if Flatpak is not active
        """
        assert get_inaccessible_paths(["/fake", "/fake_2"]) == []

    def test_flatpak_active(self, monkeypatch, home_dir, tmp_path):
        """
        Test that inaccessible paths are correctly detected when
        Flatpak is active
        """
        flatpak_info_path = tmp_path / "flatpak-info"

        flatpak_info_path.write_text(
            "[Application]\n"
            "name=fake.flatpak.Protontricks\n"
            "\n"
            "[Instance]\n"
            "flatpak-version=1.12.1\n"
            "\n"
            "[Context]\n"
            "filesystems=/mnt/SSD_A;/mnt/SSD_B;xdg-data/Steam;"
        )
        monkeypatch.setattr(
            "protontricks.flatpak.FLATPAK_INFO_PATH", str(flatpak_info_path)
        )

        inaccessible_paths = get_inaccessible_paths([
            "/mnt/SSD_A", "/mnt/SSD_C",
            str(home_dir / ".local/share/SteamOld"),
            str(home_dir / ".local/share/Steam")
        ])
        assert len(inaccessible_paths) == 2
        assert str(inaccessible_paths[0]) == "/mnt/SSD_C"
        assert str(inaccessible_paths[1]) == \
            str(Path("~/.local/share/SteamOld").expanduser())

    def test_flatpak_home(self, monkeypatch, tmp_path, home_dir):
        """
        Test that 'home' filesystem permission grants permission to the
        home directory
        """
        flatpak_info_path = tmp_path / "flatpak-info"

        flatpak_info_path.write_text(
            "[Application]\n"
            "name=fake.flatpak.Protontricks\n"
            "\n"
            "[Instance]\n"
            "flatpak-version=1.12.1\n"
            "\n"
            "[Context]\n"
            "filesystems=home;"
        )
        monkeypatch.setattr(
            "protontricks.flatpak.FLATPAK_INFO_PATH", str(flatpak_info_path)
        )

        inaccessible_paths = get_inaccessible_paths([
            "/mnt/SSD_A", "/var/fake_path",
            str(home_dir / "fake_path"),
            str(home_dir / ".local/share/FakePath")
        ])

        assert len(inaccessible_paths) == 2
        assert str(inaccessible_paths[0]) == "/mnt/SSD_A"
        assert str(inaccessible_paths[1]) == "/var/fake_path"

    def test_flatpak_home_tilde(self, monkeypatch, tmp_path, home_dir):
        """
        Test that tilde slash is expanded if included in the list of
        file systems
        """
        flatpak_info_path = tmp_path / "flatpak-info"

        flatpak_info_path.write_text(
            "[Application]\n"
            "name=fake.flatpak.Protontricks\n"
            "\n"
            "[Instance]\n"
            "flatpak-version=1.12.1\n"
            "\n"
            "[Context]\n"
            "filesystems=~/fake_path"
        )
        monkeypatch.setattr(
            "protontricks.flatpak.FLATPAK_INFO_PATH", str(flatpak_info_path)
        )

        inaccessible_paths = get_inaccessible_paths([
            str(home_dir / "fake_path"),
            str(home_dir / "fake_path_2")
        ])

        assert len(inaccessible_paths) == 1
        assert str(inaccessible_paths[0]) == str(home_dir / "fake_path_2")

    def test_flatpak_host(self, monkeypatch, tmp_path, home_dir):
        """
        Test that 'host' filesystem permission grants permission to the
        whole file system
        """
        flatpak_info_path = tmp_path / "flatpak-info"

        flatpak_info_path.write_text(
            "[Application]\n"
            "name=fake.flatpak.Protontricks\n"
            "\n"
            "[Instance]\n"
            "flatpak-version=1.12.1\n"
            "\n"
            "[Context]\n"
            "filesystems=host;"
        )
        monkeypatch.setattr(
            "protontricks.flatpak.FLATPAK_INFO_PATH", str(flatpak_info_path)
        )

        inaccessible_paths = get_inaccessible_paths([
            "/mnt/SSD_A", "/var/fake_path",
            str(home_dir / "fake_path"),
        ])

        assert len(inaccessible_paths) == 0

    @pytest.mark.usefixtures("xdg_user_dir_bin")
    def test_flatpak_xdg_user_dir(self, monkeypatch, tmp_path, home_dir):
        """
        Test that XDG filesystem permissions such as 'xdg-pictures' and
        'xdg-download' are detected correctly
        """
        flatpak_info_path = tmp_path / "flatpak-info"

        flatpak_info_path.write_text(
            "[Application]\n"
            "name=fake.flatpak.Protontricks\n"
            "\n"
            "[Instance]\n"
            "flatpak-version=1.12.1\n"
            "\n"
            "[Context]\n"
            "filesystems=xdg-pictures;"
        )
        monkeypatch.setattr(
            "protontricks.flatpak.FLATPAK_INFO_PATH", str(flatpak_info_path)
        )

        inaccessible_paths = get_inaccessible_paths([
            str(home_dir / "Pictures"),
            str(home_dir / "Download")
        ])

        assert len(inaccessible_paths) == 1
        assert str(inaccessible_paths[0]) == str(home_dir / "Download")

    def test_flatpak_unknown_permission(self, monkeypatch, tmp_path, caplog):
        """
        Test that unknown filesystem permissions are ignored
        """
        flatpak_info_path = tmp_path / "flatpak-info"

        flatpak_info_path.write_text(
            "[Application]\n"
            "name=fake.flatpak.Protontricks\n"
            "\n"
            "[Instance]\n"
            "flatpak-version=1.12.1\n"
            "\n"
            "[Context]\n"
            "filesystems=home;unknown-fs;"
        )
        monkeypatch.setattr(
            "protontricks.flatpak.FLATPAK_INFO_PATH", str(flatpak_info_path)
        )

        inaccessible_paths = get_inaccessible_paths([
            "/mnt/SSD",
        ])

        assert len(inaccessible_paths) == 1

        # Unknown filesystem permission is logged
        records = caplog.records

        assert len(records) == 1
        assert records[0].levelname == "WARNING"
        assert "Unknown Flatpak file system permission 'unknown-fs'" \
            in records[0].message
