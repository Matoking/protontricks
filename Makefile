SHELL = /bin/sh
PYTHON ?= python3
ROOT ?= /
PREFIX ?= /usr/local

install:
		${PYTHON} setup.py install --prefix="${DESTDIR}${PREFIX}" --root="${DESTDIR}${ROOT}"

		# Remove `protontricks-desktop-install`, since we already install
		# .desktop files properly
		rm "${DESTDIR}${PREFIX}/bin/protontricks-desktop-install"

		# Install the icon
		install -Dm 0644 data/icon.svg "${DESTDIR}${PREFIX}/share/icons/hicolor/scalable/apps/protontricks.svg"
