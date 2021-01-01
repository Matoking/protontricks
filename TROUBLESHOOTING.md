Troubleshooting
===============

You can [create an issue](https://github.com/Matoking/protontricks/issues/new/choose) on GitHub. Before doing so, please check if your issue is related to any of the following known issues.

# Common issues and solutions

## "warning: You are using a 64-bit WINEPREFIX"

> Whenever I run a Winetricks command, I see the warning `warning: You are using a 64-bit WINEPREFIX. Note that many verbs only install 32-bit versions of packages. If you encounter problems, please retest in a clean 32-bit WINEPREFIX before reporting a bug.`.
> Is this a problem?

Proton uses 64-bit Wine prefixes, which means you will see this warning with every game. You can safely ignore the message if the command otherwise works.

## "Unknown arg foobar"

> When I'm trying to run a Protontricks command such as `protontricks <appid> foobar`, I get the error `Unknown arg foobar`.

Your Winetricks installation might be outdated, which means your Winetricks installation doesn't support the verb you are trying to use (`foobar` in this example). Some distros such as Debian might ship very outdated versions of Winetricks. To ensure you have the latest version of Winetricks, [see the installation instructions](https://github.com/Winetricks/winetricks#installing) on the Winetricks repository.
