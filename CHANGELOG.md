# Changelog
All notable changes to this project will be documented in this file.


The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
 - protontricks is now a Python package and can be installed using `pip`.
 
### Changed
 - Argument parsing has been refactored to use argparse.
   - `protontricks gui` is now `protontricks --gui`.
   - New `protontricks --version` command to print the version number.
 - Game names are now displayed in alphabetical order and filtered to exclude non-Proton games.
 - protontricks no longer prints INFO messages by default. To restore previous behavior, use the `-v` flag.

### Fixed
 - More robust VDF parsing.
 - Corrupted appmanifest files are now skipped. See [Sirmentio/protontricks#36](https://github.com/Sirmentio/protontricks/pull/36).
 - Display a proper error message when $STEAM_DIR doesn't point to a valid Steam installation. See [Sirmentio/protontricks#46](https://github.com/Sirmentio/protontricks/issues/46).

## 1.0 - 2019-01-16
### Added
 - The last release of protontricks maintained by [@Sirmentio](https://github.com/Sirmentio).

[Unreleased]: https://github.com/Matoking/protontricks/compare/1.4.4...HEAD
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
