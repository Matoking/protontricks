protontricks
============

[![image](https://img.shields.io/pypi/v/protontricks.svg)](https://pypi.org/project/protontricks/)

A simple wrapper that does winetricks things for Proton enabled games, requires Winetricks.

This is a fork of the original project created by sirmentio. The original repository is available at [Sirmentio/protontricks](https://github.com/Sirmentio/protontricks).

# What is it?

This is a simple wrapper script that allows you to easily run Winetricks commands for Steam Play/Proton games. This is often useful when a game requires closed-source runtime libraries that are not included with Proton.

# Requirements

* Python 3.4 or newer
* Winetricks
* Steam Client Beta (comes with Proton)

# Usage

The basic usage is as follows:

```
# Find your game's App ID by searching for it
protontricks -s <GAME NAME>

# Run winetricks for the game
protontricks <APPID> <ACTIONS>

# Run a custom command within game's installation directory
protontricks -c <COMMAND> <APPID>

# Run the protontricks GUI
protontricks --gui

# Print the protontricks help message
protontricks --help
```

Since this is a wrapper, all commands that work for Winetricks will likely work for Protontricks as well.

If you have a different Steam directory, you can export ``$STEAM_DIR`` to the directory where Steam is.

If you'd like to use a local version of Winetricks, you can set ``$WINETRICKS`` to the location of your local winetricks installation. You can also set ``$PROTON_VERSION`` to a specific Proton version manually.

[Wanna see Protontricks in action?](https://asciinema.org/a/229323)

# Installation

You can install Protontricks using an unofficial package or **pipx**. **pip** can also be used, but it is not recommended due to possible problems.

## Unofficial packages (recommended)

Unofficial packages allow easier installation and updates using distro-specific package managers. Unofficial packages are maintained by community members and might be out-of-date compared to releases on PyPI.

* Arch Linux ([release](https://aur.archlinux.org/packages/protontricks/), [git](https://aur.archlinux.org/packages/protontricks-git/))

If you maintain an unofficial package for Protontricks, feel free to create a pull request adding an entry to this section!

## pipx (recommended)

You can use pipx to install the latest version on PyPI or the git repository for the current user. Installing protontricks using pipx is recommended if an unofficial package doesn't exist for your Linux distro.

**pipx requires Python 3.6 or newer.**

**You will need to install pip, setuptools and virtualenv first.** Install the correct packages depending on your distribution:

* Arch Linux: `sudo pacman -S python-pip python-setuptools python-virtualenv`
* Debian-based (Ubuntu, Linux Mint): `sudo apt install python3-pip python3-setuptools python3-venv`
* Fedora: `sudo dnf install python3-pip python3-setuptools python3-libs`

After installing pip and virtualenv, run the following commands to install pipx for the current user.

```sh
python3 -m pip install --user pipx
~/.local/bin/pipx ensurepath
```

Close and reopen your terminal. After that, you can install protontricks.

```sh
pipx install protontricks
```

To upgrade to the latest release:
```sh
pipx upgrade protontricks
```

To install the latest development version (requires `git`):
```sh
pipx install --spec git+https://github.com/Matoking/protontricks.git protontricks
```

## pip (not recommended)

You can use pip to install the latest version on PyPI or the git repository. This method should work in any system where Python 3 is available.

**Note that this installation method might cause conflicts with your distro's package manager. To prevent this, consider using the pipx method or an unofficial package instead.**

**You will need to install pip and setuptools first.** Install the correct packages depending on your distribution:

* Arch Linux: `sudo pacman -S python-pip python-setuptools`
* Debian-based (Ubuntu, Linux Mint): `sudo apt install python3-pip python3-setuptools`
* Fedora: `sudo dnf install python3-pip python3-setuptools`

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
