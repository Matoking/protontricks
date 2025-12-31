SHELL = /bin/sh
PYTHON ?= python3
ROOT ?= /
PREFIX ?= /usr/local

install:
		${PYTHON} setup.py install --prefix="${DESTDIR}${PREFIX}" --root="${DESTDIR}${ROOT}"

		# Remove `protontricks-desktop-install`, since we already install
		# .desktop files properly
		rm "${DESTDIR}${PREFIX}/bin/protontricks-desktop-install"

		# Argument auto completion
		#
		# Argument auto completion (bash)
		mkdir -p "${DESTDIR}${PREFIX}/share/bash-completion/completions"
		register-python-argcomplete --shell bash protontricks > "${DESTDIR}${PREFIX}/share/bash-completion/completions/protontricks"
		register-python-argcomplete --shell bash protontricks-launch > "${DESTDIR}${PREFIX}/share/bash-completion/completions/protontricks-launch"

		# Argument auto completion (zsh)
		# Automatic shell sorting is disabled since we want the sorting for
		# `<APPID>` to be sorted by the application name, not the numeric app
		# ID
		mkdir -p "${DESTDIR}${PREFIX}/share/zsh/vendor-completions"
		register-python-argcomplete --shell zsh protontricks --complete-arguments -o nosort > "${DESTDIR}${PREFIX}/share/zsh/vendor-completions/protontricks"
		register-python-argcomplete --shell zsh protontricks-launch --complete-arguments -o nosort > "${DESTDIR}${PREFIX}/share/zsh/vendor-completions/protontricks-launch"

		# Argument auto completion (fish)
		mkdir -p "${DESTDIR}${PREFIX}/share/fish/vendor_completions.d"
		register-python-argcomplete --shell fish protontricks > "${DESTDIR}${PREFIX}/share/fish/vendor_completions.d/protontricks.fish"
		register-python-argcomplete --shell fish protontricks-launch > "${DESTDIR}${PREFIX}/share/fish/vendor_completions.d/protontricks-launch.fish"

		# HACK: Disable shell auto-sorting by patching the `complete` command.
		# `--complete-arguments` is not supported for `--shell fish`.
		sed -i "s/complete --command protontricks/complete --command protontricks --keep-order/" "${DESTDIR}${PREFIX}/share/fish/vendor_completions.d/protontricks.fish"
		sed -i "s/complete --command protontricks-launch/complete --command protontricks-launch --keep-order/" "${DESTDIR}${PREFIX}/share/fish/vendor_completions.d/protontricks-launch.fish"
