from setuptools import setup

import versioneer


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
    version=versioneer.get_version(),
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    python_requires=">=3.4",
    url=URL,
    packages=["protontricks"],
    package_data={"": ["LICENSE"]},
    package_dir={"protontricks": "src/protontricks"},
    install_requires=[
        "vdf>=2.4"
    ],
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
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7'
    ],
    cmdclass=versioneer.get_cmdclass()
)

