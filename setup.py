from setuptools import setup


DESCRIPTION = (
    "A simple wrapper for running Winetricks commands for Proton-enabled "
    "games."
)
LONG_DESCRIPTION = (
    "A simple wrapper for running Winetricks commands for Proton-enabled "
    "games. Protontricks requires Winetricks."
)
AUTHOR = "Janne Pulkkinen"
AUTHOR_EMAIL = "janne.pulkkinen@protonmail.com"
URL = "https://github.com/Matoking/protontricks"


setup(
    name="protontricks",
    use_scm_version={
        "write_to": "src/protontricks/_version.py"
    },
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    data_files=[
        (
            "share/applications",
            [
                ("src/protontricks/data/share/applications/"
                 "protontricks.desktop"),
                ("src/protontricks/data/share/applications/"
                 "protontricks-launch.desktop")
            ]
        )
    ],
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    python_requires=">=3.6",
    url=URL,
    packages=["protontricks"],
    package_data={"": ["LICENSE"]},
    package_dir={"protontricks": "src/protontricks"},
    install_requires=[
        "setuptools",  # Required for pkg_resources
        "vdf>=3.2"
    ],
    entry_points={
        "console_scripts": [
            "protontricks = protontricks.cli.main:cli",
            "protontricks-launch = protontricks.cli.launch:cli",
            # `protontricks-desktop-install` is only responsible for installing
            # .desktop files and should be omitted if the distro package
            # already ships .desktop files properly
            ("protontricks-desktop-install "
             "= protontricks.cli.desktop_install:cli")
        ]
    },
    include_package_data=True,
    license="GPL3",
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Topic :: Utilities',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11'
    ],
)
