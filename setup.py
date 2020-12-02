from setuptools import setup


DESCRIPTION = (
    "A simple wrapper for running Winetricks commands for Proton-enabled "
    "games."
)
LONG_DESCRIPTION = (
    "A simple wrapper for running Winetricks commands for Proton-enabled "
    "games. protontricks requires Winetricks."
)
AUTHOR = "Janne Pulkkinen"
AUTHOR_EMAIL = "jannepulk@gmail.com"
URL = "https://github.com/Matoking/protontricks"


setup(
    name="protontricks",
    use_scm_version={
        "write_to": "src/protontricks/_version.py"
    },
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    python_requires=">=3.5",
    url=URL,
    packages=["protontricks"],
    package_data={"": ["LICENSE"]},
    package_dir={"protontricks": "src/protontricks"},
    setup_requires=["setuptools_scm"],
    install_requires=["vdf>=3.2"],
    entry_points={
        "console_scripts": [
            "protontricks = protontricks.cli:main"
        ]
    },
    include_package_data=True,
    license="GPL3",
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Topic :: Utilities',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9'
    ],
)
