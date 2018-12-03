# protontricks
A simple wrapper that does winetricks things for Proton enabled games, requires Winetricks.

# What is it?
This is a simple wrapper script that uses Winetricks to allow you to specify the game's App ID rather than the full length directory to the Proton prefix itself, I thought this would be easier for some so I decided to upload it for everyone to use!

# Requirements
* Python 3 or newer
* Winetricks
* The Steam beta

# Usage
The basic usage is as follows:

```
# Find your game's App ID by searching for it
protontricks -s <GAME NAME>

# Run winetricks for the game
protontricks <APPID> <ACTIONS>

# Run the protontricks GUI
protontricks gui
```

Since this is a wrapper, all syntax that works for Winetricks will potentially work for Protontricks.

If you have a different Steam directory (Like I do due to Arch's silly directory tomfoolery), you can export ``$STEAM_DIR`` to the directory where Steam is.

If you'd like to use a local version of Winetricks, you can set ``$WINETRICKS`` to the location of your local winetricks installation. As well, you can set ``$PROTON_VERSION`` to a specific version manually.

[Wanna see Protontricks in action?](https://asciinema.org/a/i2uqz1uZXYACl9NAHYbuZ3TCT)

# Installation
I'd say the easiest way to install is by doing the following commands:
```sh
wget https://raw.githubusercontent.com/Sirmentio/protontricks/master/protontricks && chmod +x protontricks
sudo mv protontricks /usr/bin/protontricks
```
## Unofficial packages
Currently, the following is the current unofficial packages that can make installing and updating much easier. These are not maintained by me because I currently don't have the capacity of knowing how to make distro packages. Feel free to contribute and try to maintain your own distro packages and add them here.
* [Arch Linux](https://aur.archlinux.org/packages/protontricks-git/)
* Ubuntu (Nonexistent?)

# Contact
If you'd like, you can hit me up on twitter @Sirmentio, or on the Linux Gaming Discord, I don't talk much there but I'd be happy to hear from anyone who has something to say!
