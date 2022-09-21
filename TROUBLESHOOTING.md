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

## "Unknown option --foobar"

> When I'm trying to run a Protontricks command such as `protontricks <appid> --no-bwrap foobar`, I get the error `Unknown option --no-bwrap`.

You need to provide Protontricks specific options *before* the app ID. This is because all parameters after the app ID are passed directly to Winetricks; otherwise, Protontricks cannot tell which options are related to Winetricks and which are not. In this case, the correct command to run would be `protontricks --no-bwrap <appid> foobar`.

## "command cabextract ... returned status 1. Aborting."

> When I'm trying to run a Winetricks command, I get the error `command cabextract ... returned status 1. Aborting.`

This is a known issue with `cabextract`, which doesn't support symbolic links created by Proton 5.13 and newer.

As a workaround, you can remove the problematic symbolic link in the failed command and run the command again. Repeat this until the command finishes successfully.

You can also check [the Winetricks issue on GitHub](https://github.com/Winetricks/winetricks/issues/1648).
