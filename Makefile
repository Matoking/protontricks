PYTHON ?= python3
ROOT ?= /
PREFIX ?= /usr/local

install:
		${PYTHON} setup.py install --prefix="${PREFIX}" --root="${ROOT}"

		desktop-file-install --dir "${PREFIX}/usr/local/share/applications/" \
			src/protontricks/data/protontricks.desktop \
			src/protontricks/data/protontricks-launch.desktop

		# Remove `protontricks-desktop-install`, since we already install
		# .desktop files properly
		rm "${PREFIX}/bin/protontricks-desktop-install"
