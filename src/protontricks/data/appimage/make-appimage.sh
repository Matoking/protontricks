#!/bin/sh

set -eu

ARCH=$(uname -m)
VERSION=$(pacman -Q protontricks | awk '{print $2; exit}') # example command to get version of application here
export ARCH VERSION

SHARUN="https://raw.githubusercontent.com/pkgforge-dev/Anylinux-AppImages/refs/heads/main/useful-tools/quick-sharun.sh"
DEBLOATED_PKGS="https://raw.githubusercontent.com/pkgforge-dev/Anylinux-AppImages/refs/heads/main/useful-tools/get-debloated-pkgs.sh"

export OUTPATH=./dist
export ADD_HOOKS="self-updater.bg.hook"
export UPINFO="gh-releases-zsync|${GITHUB_REPOSITORY%/*}|${GITHUB_REPOSITORY#*/}|latest|*$ARCH.AppImage.zsync"
export ICON=/usr/share/icons/hicolor/scalable/apps/com.github.Matoking.protontricks.svg
export DESKTOP=/usr/share/applications/protontricks.desktop
export LIB_DIR=/usr/lib
export DEPLOY_PYTHON=1
export DEPLOY_OPENGL=1
export DEPLOY_VULKAN=1

#Remove leftovers
rm -rf AppDir dist

# ADD LIBRARIES
wget --retry-connrefused --tries=30 "$SHARUN" -O ./quick-sharun
wget --retry-connrefused --tries=30 "$DEBLOATED_PKGS" -O ./get-debloated-pkgs
chmod +x ./quick-sharun ./get-debloated-pkgs

# Debloated pkgs
./get-debloated-pkgs --add-common --prefer-nano

# Deploy dependencies
./quick-sharun \
	/usr/bin/*tricks*        \
	/usr/lib/libopenjp2.so*  \
	/usr/lib/libtiff.so*     \
	/usr/lib/libimagequant.so* \
	/usr/bin/zenity \
	/usr/bin/yad

echo 'unset VK_DRIVER_FILES' >> ./AppDir/.env

cc -shared -fPIC -O2 -o ./AppDir/lib/execve-sharun-hack.so execve-sharun-hack.c -ldl
echo 'execve-sharun-hack.so' >> ./AppDir/.preload
echo 'export ANYLINUX_EXECVE_WRAP_PATHS="$DATADIR:$HOME/.steam"' >> ./AppDir/bin/execve-wrap-path.hook

# Additional changes can be done in between here

# Turn AppDir into AppImage
./quick-sharun --make-appimage
