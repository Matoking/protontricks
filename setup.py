from setuptools import setup


setup(
    # This is considered deprecated since Python wheels don't provide a way
    # to install package-related files outside the package directory
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
    ]
)
