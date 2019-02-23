# protontricks
This is a fork of the original project created by sirmentio.
The original repository is available at [Sirmentio/protontricks](https://github.com/Sirmentio/protontricks).

A simple wrapper that does winetricks things for Proton enabled games, requires Winetricks.

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

Since this is a wrapper, all commands that work for Winetricks will likely work for Protontricks as well

If you have a different Steam directory, you can export ``$STEAM_DIR`` to the directory where Steam is.

If you'd like to use a local version of Winetricks, you can set ``$WINETRICKS`` to the location of your local winetricks installation. You can also set ``$PROTON_VERSION`` to a specific Proton version manually.

[Wanna see Protontricks in action?](https://asciinema.org/a/229323)

# Installation
You can easily install the latest development version using `pip`
(included with all Python 3.4+ installations):
```sh
python3 -m pip install git+https://github.com/Matoking/protontricks.git
```

Or if you only want to install protontricks for the local user:
```sh
python3 -m pip install --user git+https://github.com/Matoking/protontricks.git
```

If you want to install a specific version (in this case **1.1.1**):
```sh
python3 -m pip install git+https://github.com/Matoking/protontricks.git@1.1.1
```
