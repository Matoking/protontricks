# Changelog
All notable changes to this project will be documented in this file.


The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]
### Added
 - Custom Proton installations in `STEAM_DIR/compatibilitytools.d` are now detected. See [Sirmentio/protontricks#31](https://github.com/Sirmentio/protontricks/issues/31).
 - protontricks is now a Python package and can be installed using `pip`.
 
### Changed
 - `protontricks gui` is now `protontricks --gui`.
 - Game names are now displayed in sorted order.
 - protontricks no longer prints INFO messages by default. To restore previous behavior, use the `-v` flag.

### Fixed
 - More robust VDF parsing.
 - Corrupted appmanifest files are now skipped. See [Sirmentio/protontricks#36](https://github.com/Sirmentio/protontricks/pull/36).

## [1.0] - 2019-01-16
### Added
 - The last release of protontricks maintained by [@Sirmentio](https://github.com/Sirmentio).
