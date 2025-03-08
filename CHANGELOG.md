# Changelog
All notable changes to this project will be documented in this file.


The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.12.1] - 2025-03-08
### Fixed
 - Fix missing app icons for games installed using newer Steam client
 - Fix spurious "unknown file arch" Winetricks warnings (newer Winetricks required)

### Removed
 - Drop Python 3.6 support

## [1.12.0] - 2024-09-16
### Added
 - `--cwd-app` flag to set working directory to the game's installation directory
 - Add support for Snap Steam installations

### Changed
 - `protontricks -c` and `protontricks-launch` now use the current working directory instead of the game's installation directory. `--cwd-app` can be used to restore old behavior. Scripts can also `$STEAM_APP_PATH` environment variable to determine the game's installation directory; this has been supported (albeit undocumented) since 1.8.0.
 - `protontricks` will now launch GUI if no arguments were provided

### Fixed
 - Fix crash when parsing appinfo.vdf V29 in new Steam client version
 - Fix Protontricks crash when `config.vdf` contains invalid Unicode characters

> [!IMPORTANT]
> This release bundles a patched version of `vdf` in case the system Python package doesn't have the required `appinfo.vdf` V29 support.
> If you're a package maintainer, you will probably want to remove the corresponding
> commit if the distro you're using already ships a version of `vdf` with the
> required support.

## [1.11.1] - 2024-02-20
### Fixed
 - Fix Protontricks crash when custom Proton has an invalid or empty `compatibilitytool.vdf` manifest
 - Fix Protontricks GUI crash when Proton installation is incomplete
 - Check if Steam Runtime launcher service launched correctly instead of always assuming successful launch

## [1.11.0] - 2023-12-30
### Added
 - Show app icons for custom shortcuts in the app selector
 - Verbose flag can be enabled with `-vv` for additional debug logging

### Fixed
 - Fix Protontricks not recognizing supported Steam Runtime installation due to changed name
 - Fix Protontricks not recognizing default Proton installation for games with different Proton preselected by Valve testing
 - Fix Protontricks crash when app has an unidentifiable app icon

## [1.10.5] - 2023-09-05
### Fixed
 - Fix crash caused by custom app icons with non-RGB mode

## [1.10.4] - 2023-08-26
### Fixed
 - Fix crash caused by the Steam shortcut configuration file containing extra data after the VDF section
 - Fix differently sized custom app icons breaking the layout in the app selector

## [1.10.3] - 2023-05-06
### Added
 - Flatpak version of Steam is also detected with non-Flatpak installation of Protontricks

### Changed
 - `--background-wineserver` is now disabled by default due to problems with crashing graphical applications and broken console output

### Fixed
 - Fix detection of Steam library folders using non-standard capitalizations for `steamapps`
 - _Steam Linux Runtime - Sniper_ is no longer incorrectly reported as an unsupported runtime

## [1.10.2] - 2023-02-13
### Added
 - Launch application with fixed locale settings if Steam Deck is used and non-existent locales are configured

### Fixed
 - Fix crashes caused by missing permissions when checking for Steam apps

## [1.10.1]- 2022-12-10
### Fixed
 - Fix crash when unknown XDG Flatpak filesystem permissions are enabled
 - Fix crash when parsing appinfo.vdf V28 version introduced in Steam beta

## [1.10.0] - 2022-11-27
### Added
 - Prompt the user for a Steam installation if multiple installations are found

### Fixed
 - Detect XDG user directory permissions in Flatpak environment

## [1.9.2] - 2022-09-16
### Fixed
 - Fix random crashes when running Wine commands due to race condition in Wine launcher script

## [1.9.1] - 2022-08-28
### Added
 - Print a warning when multiple Steam directories are detected and `STEAM_DIR` is not used to specify the directory
 
### Changed
 - Launch Steam Runtime sandbox with `--bus-name` parameter instead of the now deprecated `--socket`

### Fixed
 - Fix various crashes due to Wine processes under Steam Runtime sandbox using the incorrect working directory

## [1.9.0] - 2022-07-02
### Added
 - Add `-l/--list` command to list all games

### Fixed
 - Fix `wineserver -w` calls hanging when legacy Steam Runtime and background wineserver are enabled
 - Do not attempt to launch bwrap-launcher if bwrap is not available

## [1.8.2] - 2022-05-16
### Fixed
 - Fix Wine crash on newer Steam Runtime installations due to renamed runtime executable
 - Fix graphical Wine applications crashing on Wayland
 - Fix Protontricks crash caused by Steam shortcuts created by 3rd party applications such as Lutris

## [1.8.1] - 2022-03-20
### Added
 - Prompt the user to update Flatpak permissions if inaccessible paths are detected

### Fixed
 - Fix Proton discovery on Steam Deck

### Removed
 - Drop Python 3.5 support

## [1.8.0] - 2022-02-26
### Added
 - fsync/esync is enabled by default
 - `PROTON_NO_FSYNC` and `PROTON_NO_ESYNC` environment variables are supported
 - Improve Wine command startup time by launching a background wineserver for the duration of the Protontricks session. This is enabled by default for bwrap, and can also be toggled manually with `--background-wineserver/--no-background-wineserver`.
 - Improve Wine command startup time with bwrap by creating a single container and launching all Wine processes inside it.

### Fixed
 - Fix Wine crash when the Steam application and Protontricks are running at the same time
 - Fix Steam installation detection when both non-Flatpak and Flatpak versions of Steam are installed for the same user
 - Fix Protontricks crash when Proton installation is incomplete
 - Fix Protontricks crash when both Flatpak and non-Flatpak versions of Steam are installed
 - Fix duplicate log messages when using `protontricks-launch`
 - Fix error dialog not being displayed when using `protontricks-launch`

## [1.7.0] - 2022-01-08
### Changed
 - Enable usage of Flatpak Protontricks with non-Flatpak Steam. Flatpak Steam is prioritized if both are found.

### Fixed
 - bwrap is only disabled when the Flatpak installation is too old. Flatpak 1.12.1 and newer support sub-sandboxes.
 - Remove Proton installations from app listings

## [1.6.2] - 2021-11-28
### Changed
 - Return code is now returned from the executed user commands
 - Return code `1` is returned for most Protontricks errors instead of `-1`

## [1.6.1] - 2021-10-18
### Fixed
 - Fix duplicate Steam application entries
 - Fix crash on Python 3.5

## [1.6.0] - 2021-08-08
### Added
 - Add `protontricks-launch` script to launch Windows executables using Proton app specific Wine prefixes
 - Add desktop integration for Windows executables, which can now be launched using Protontricks
 - Add `protontricks-desktop-install` to install desktop integration for the local user. This is only necessary if the installation method doesn't do this automatically.
 - Add error dialog for displaying error information when Protontricks has been launched from desktop and no user-visible terminal is available.
 - Add YAD as GUI provider. YAD is automatically used instead of Zenity when available as it supports additional features.

### Changed
 - Improved GUI dialog. The prompt to select the Steam app now uses a list dialog with support for scrolling, search and app icons. App icons are only supported on YAD.

### Fixed
 - Display proper error messages in certain cases when corrupted VDF files are found
 - Fix crash caused by appmanifest files that can't be read due to insufficient permissions
 - Fix crash caused by non-Proton compatibility tool being enabled for the selected app
 - Fix erroneous warning when Steam library is inside a case-insensitive file system

## [1.5.2] - 2021-06-09
### Fixed
 - Custom Proton installations now use Steam Runtime installations when applicable
 - Fix crash caused by older Steam app installations using a different app manifest structure
 - Fix crash caused by change to lowercase field names in multiple VDF files
 - Fix crash caused by change in the Steam library folder configuration file

## [1.5.1] - 2021-05-10
### Fixed
 - bwrap containerization now tries to mount more root directories except those that have been blacklisted due to potential issues

## [1.5.0] - 2021-04-10
### Added
 - Use bwrap containerization with newer Steam Runtime installations. The old behavior can be enabled with `--no-bwrap` in case of problems.

### Fixed
 - User-provided `WINE` and `WINESERVER` environment variables are used when Steam Runtime is enabled
 - Fixed crash caused by changed directory name in Proton Experimental update

## [1.4.4] - 2021-02-03
### Fixed
 - Display a proper error message when Proton installation is incomplete due to missing Steam Runtime
 - Display a proper warning when a tool manifest is empty
 - Fix crash caused by changed directory structure in Steam Runtime update

## [1.4.3] - 2020-12-09
### Fixed
 - Add support for newer Steam Runtime versions

## [1.4.2] - 2020-09-19
### Fixed
 - Fix crash with newer Steam client beta caused by differently cased keys in `loginusers.vdf`

### Added
 - Print a warning if both `steamapps` and `SteamApps` directories are found inside the same library directory

### Changed
 - Print full help message when incorrect parameters are provided.

## [1.4.1] - 2020-02-17
### Fixed
 - Fixed crash caused by Steam library paths containing special characters
 - Fixed crash with Proton 5.0 caused by Steam Runtime being used unnecessarily with all binaries

## [1.4] - 2020-01-26
### Added
 - System-wide compatibility tool directories are now searched for Proton installations

### Changed
 - Drop Python 3.4 compatibility. Python 3.4 compatibility has been broken since 1.2.2.

### Fixed
 - Zenity no longer crashes the script if locale is incapable of processing the arguments.
 - Selecting "Cancel" in the GUI window now prints a proper message instead of an error.
 - Add workaround for Zenity crashes not handled by the previous fix

## [1.3.1] - 2019-11-21
### Fixed
 - Fix Proton prefix detection when the prefix directory is located inside a `SteamApps` directory instead of `steamapps`
 - Use the most recently used Proton prefix when multiple prefix directories are found for a single game
 - Fix Python 3.5 compatibility

## [1.3] - 2019-11-06
### Added
 - Non-Steam applications are now detected.

### Fixed
 - `STEAM_DIR` environment variable will no longer fallback to default path in some cases

## [1.2.5] - 2019-09-17
### Fixed
 - Fix regression in 1.2.3 that broke detection of custom Proton installations.
 - Proton prefix is detected correctly even if it exists in a different Steam library folder than the game installation.

## [1.2.4] - 2019-07-25
### Fixed
 - Add a workaround for a VDF parser bug that causes a crash when certain appinfo.vdf files are parsed.

## [1.2.3] - 2019-07-18
### Fixed
 - More robust parsing of appinfo.vdf. This fixes some cases where Protontricks was unable to detect Proton installations.

## [1.2.2] - 2019-06-05
### Fixed
 - Set `WINEDLLPATH` and `WINELOADER` environment variables.
 - Add a workaround for a Zenity bug that causes the GUI to crash when certain versions of Zenity are used.

## [1.2.1] - 2019-04-08
### Changed
 - Delay Proton detection until it's necessary.

### Fixed
 - Use the correct Proton installation when selecting a Steam app using the GUI.
 - Print a proper error message if Steam isn't found.
 - Print an error message when GUI is enabled and no games were found.
 - Support appmanifest files with mixed case field names.

## [1.2] - 2019-02-27
### Added
 - Add a `-c` parameter to run shell commands in the game's installation directory with relevant Wine environment variables.
 - Steam Runtime is now supported and used by default unless disabled with `--no-runtime` flag or `STEAM_RUNTIME` environment variable.

### Fixed
 - All arguments are now correctly passed to winetricks.
 - Games that haven't been launched at least once are now excluded properly.
 - Custom Proton versions with custom display names now work properly.
 - `PATH` environment variable is modified to prevent conflicts with system-wide Wine binaries.
 - Steam installation is handled correctly if `~/.steam/steam` and `~/.steam/root` point to different directories.

## [1.1.1] - 2019-01-20
### Added
 - Game-specific Proton installations are now detected.

### Fixed
 - Proton installations are now detected properly again in newer Steam Beta releases.

## [1.1] - 2019-01-20
### Added
 - Custom Proton installations in `STEAM_DIR/compatibilitytools.d` are now detected. See [Sirmentio/protontricks#31](https://github.com/Sirmentio/protontricks/issues/31).
 - Protontricks is now a Python package and can be installed using `pip`.
 
### Changed
 - Argument parsing has been refactored to use argparse.
   - `protontricks gui` is now `protontricks --gui`.
   - New `protontricks --version` command to print the version number.
 - Game names are now displayed in alphabetical order and filtered to exclude non-Proton games.
 - Protontricks no longer prints INFO messages by default. To restore previous behavior, use the `-v` flag.

### Fixed
 - More robust VDF parsing.
 - Corrupted appmanifest files are now skipped. See [Sirmentio/protontricks#36](https://github.com/Sirmentio/protontricks/pull/36).
 - Display a proper error message when $STEAM_DIR doesn't point to a valid Steam installation. See [Sirmentio/protontricks#46](https://github.com/Sirmentio/protontricks/issues/46).

## 1.0 - 2019-01-16
### Added
 - The last release of Protontricks maintained by [@Sirmentio](https://github.com/Sirmentio).

[Unreleased]: https://github.com/Matoking/protontricks/compare/1.12.1...HEAD
[1.12.1]: https://github.com/Matoking/protontricks/compare/1.12.0...1.12.1
[1.12.0]: https://github.com/Matoking/protontricks/compare/1.11.1...1.12.0
[1.11.1]: https://github.com/Matoking/protontricks/compare/1.11.0...1.11.1
[1.11.0]: https://github.com/Matoking/protontricks/compare/1.10.5...1.11.0
[1.10.5]: https://github.com/Matoking/protontricks/compare/1.10.4...1.10.5
[1.10.4]: https://github.com/Matoking/protontricks/compare/1.10.3...1.10.4
[1.10.3]: https://github.com/Matoking/protontricks/compare/1.10.2...1.10.3
[1.10.2]: https://github.com/Matoking/protontricks/compare/1.10.1...1.10.2
[1.10.1]: https://github.com/Matoking/protontricks/compare/1.10.0...1.10.1
[1.10.0]: https://github.com/Matoking/protontricks/compare/1.9.2...1.10.0
[1.9.2]: https://github.com/Matoking/protontricks/compare/1.9.1...1.9.2
[1.9.1]: https://github.com/Matoking/protontricks/compare/1.9.0...1.9.1
[1.9.0]: https://github.com/Matoking/protontricks/compare/1.8.2...1.9.0
[1.8.2]: https://github.com/Matoking/protontricks/compare/1.8.1...1.8.2
[1.8.1]: https://github.com/Matoking/protontricks/compare/1.8.0...1.8.1
[1.8.0]: https://github.com/Matoking/protontricks/compare/1.7.0...1.8.0
[1.7.0]: https://github.com/Matoking/protontricks/compare/1.6.2...1.7.0
[1.6.2]: https://github.com/Matoking/protontricks/compare/1.6.1...1.6.2
[1.6.1]: https://github.com/Matoking/protontricks/compare/1.6.0...1.6.1
[1.6.0]: https://github.com/Matoking/protontricks/compare/1.5.2...1.6.0
[1.5.2]: https://github.com/Matoking/protontricks/compare/1.5.1...1.5.2
[1.5.1]: https://github.com/Matoking/protontricks/compare/1.5.0...1.5.1
[1.5.0]: https://github.com/Matoking/protontricks/compare/1.4.4...1.5.0
[1.4.4]: https://github.com/Matoking/protontricks/compare/1.4.3...1.4.4
[1.4.3]: https://github.com/Matoking/protontricks/compare/1.4.2...1.4.3
[1.4.2]: https://github.com/Matoking/protontricks/compare/1.4.1...1.4.2
[1.4.1]: https://github.com/Matoking/protontricks/compare/1.4...1.4.1
[1.4]: https://github.com/Matoking/protontricks/compare/1.3.1...1.4
[1.3.1]: https://github.com/Matoking/protontricks/compare/1.3...1.3.1
[1.3]: https://github.com/Matoking/protontricks/compare/1.2.5...1.3
[1.2.5]: https://github.com/Matoking/protontricks/compare/1.2.4...1.2.5
[1.2.4]: https://github.com/Matoking/protontricks/compare/1.2.3...1.2.4
[1.2.3]: https://github.com/Matoking/protontricks/compare/1.2.2...1.2.3
[1.2.2]: https://github.com/Matoking/protontricks/compare/1.2.1...1.2.2
[1.2.1]: https://github.com/Matoking/protontricks/compare/1.2...1.2.1
[1.2]: https://github.com/Matoking/protontricks/compare/1.1.1...1.2
[1.1.1]: https://github.com/Matoking/protontricks/compare/1.1...1.1.1
[1.1]: https://github.com/Matoking/protontricks/compare/1.0...1.1
