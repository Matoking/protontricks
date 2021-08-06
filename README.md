protontricks
============

[![image](https://img.shields.io/pypi/v/protontricks.svg)](https://pypi.org/project/protontricks/)
[![Coverage Status](https://coveralls.io/repos/github/Matoking/protontricks/badge.svg?branch=master)](https://coveralls.io/github/Matoking/protontricks?branch=master)
[![Build Status](https://travis-ci.com/Matoking/protontricks.png?branch=master)](https://travis-ci.com/Matoking/protontricks)

A simple wrapper that does winetricks things for Proton enabled games, requires Winetricks.

This is a fork of the original project created by sirmentio. The original repository is available at [Sirmentio/protontricks](https://github.com/Sirmentio/protontricks).

# What is it?

This is a simple wrapper script that allows you to easily run Winetricks commands for Steam Play/Proton games. This is often useful when a game requires closed-source runtime libraries that are not included with Proton.

# Requirements

* Python 3.5 or newer
* Winetricks
* Steam
* YAD (recommended) **or** Zenity. Required for GUI.

# Usage

The basic usage is as follows:

```
# Find your game's App ID by searching for it
protontricks -s <GAME NAME>

# Run winetricks for the game.
# Any parameters in <ACTIONS> are passed directly to Winetricks.
# Parameters specific to Protontricks need to be placed *before* <APPID>.
protontricks <APPID> <ACTIONS>

# Run a custom command within game's installation directory
protontricks -c <COMMAND> <APPID>

# Run the protontricks GUI
protontricks --gui

# Print the protontricks help message
protontricks --help
```

Protontricks also comes with an application shortcut and desktop integration, adding a Protontricks app shortcut and the ability to launch individual EXE files using Protontricks. Depending on your installation method, you may also need to run `protontricks-desktop-install` to enable this functionality.

Since this is a wrapper, all commands that work for Winetricks will likely work for Protontricks as well.

If you have a different Steam directory, you can export ``$STEAM_DIR`` to the directory where Steam is.

If you'd like to use a local version of Winetricks, you can set ``$WINETRICKS`` to the location of your local winetricks installation.

You can also set ``$PROTON_VERSION`` to a specific Proton version manually. This is usually the name of the Proton installation without the revision version number. For example, if Steam displays the name as `Proton 5.0-3`, use `Proton 5.0` as the value for `$PROTON_VERSION`.

[Wanna see Protontricks in action?](https://asciinema.org/a/229323)

# Troubleshooting

For common issues and solutions, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

# Installation

You can install Protontricks using an unofficial package or **pipx**. **pip** can also be used, but it is not recommended due to possible problems.

**If you're using the Flatpak version of Steam**, follow the [Flatpak-specific installation instructions](https://github.com/flathub/com.valvesoftware.Steam.Utility.protontricks) instead.

Unless you're using unofficial packages, **you may need to install Winetricks separately**. See the [installation instructions](https://github.com/Winetricks/winetricks#installing) for further details.

## Unofficial packages (recommended)

Unofficial packages allow easier installation and updates using distro-specific package managers. Unofficial packages are maintained by community members and might be out-of-date compared to releases on PyPI.

* Arch Linux ([release](https://aur.archlinux.org/packages/protontricks/), [git](https://aur.archlinux.org/packages/protontricks-git/))
* Fedora ([release](https://src.fedoraproject.org/rpms/protontricks))
* NixOS ([nixpkgs](https://github.com/NixOS/nixpkgs/blob/master/pkgs/tools/package-management/protontricks/default.nix))
* Void Linux ([void-packages](https://github.com/void-linux/void-packages/blob/master/srcpkgs/protontricks/template))

[![Packaging status](https://repology.org/badge/vertical-allrepos/protontricks.svg)](https://repology.org/project/protontricks/versions)

If you maintain an unofficial package for Protontricks, feel free to create a pull request adding an entry to this section!

## pipx (recommended)

You can use pipx to install the latest version on PyPI or the git repository for the current user. Installing protontricks using pipx is recommended if an unofficial package doesn't exist for your Linux distro.

**pipx requires Python 3.6 or newer.**

**You will need to install pip, setuptools and virtualenv first.** Install the correct packages depending on your distribution:

* Arch Linux: `sudo pacman -S python-pip python-pipx python-setuptools python-virtualenv`
* Debian-based (Ubuntu, Linux Mint): `sudo apt install python3-pip python3-setuptools python3-venv pipx`
* Fedora: `sudo dnf install python3-pip python3-setuptools python3-libs pipx`
* Gentoo:

  ```sh
  sudo emerge -av dev-python/pip dev-python/virtualenv dev-python/setuptools
  python3 -m pip install --user pipx
  ~/.local/bin/pipx ensurepath
  ```

Close and reopen your terminal. After that, you can install protontricks.

```sh
pipx install protontricks
```

To enable desktop integration as well, run the following command *after* installing Protontricks

```sh
protontricks-desktop-install
```

To upgrade to the latest release:
```sh
pipx upgrade protontricks
```

To install the latest development version (requires `git`):
```sh
pipx install git+https://github.com/Matoking/protontricks.git
# '--spec' is required for older versions of pipx
pipx install --spec git+https://github.com/Matoking/protontricks.git protontricks
```

## pip (not recommended)

You can use pip to install the latest version on PyPI or the git repository. This method should work in any system where Python 3 is available.

**Note that this installation method might cause conflicts with your distro's package manager. To prevent this, consider using the pipx method or an unofficial package instead.**

**You will need to install pip and setuptools first.** Install the correct packages depending on your distribution:

* Arch Linux: `sudo pacman -S python-pip python-setuptools`
* Debian-based (Ubuntu, Linux Mint): `sudo apt install python3-pip python3-setuptools`
* Fedora: `sudo dnf install python3-pip python3-setuptools`
* Gentoo: `sudo emerge -av dev-python/pip dev-python/setuptools`

To install the latest release using `pip`:
```sh
sudo python3 -m pip install protontricks
```

To upgrade to the latest release:
```sh
sudo python3 -m pip install --upgrade protontricks
```

To install protontricks only for the current user:
```sh
python3 -m pip install --user protontricks
```

To install the latest development version (requires `git`):
```sh
sudo python3 -m pip install git+https://github.com/Matoking/protontricks.git
```
