from glob import glob
from setuptools import find_packages, setup


package_name = "so101_moveit_config"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/config", glob("config/*")),
        (f"share/{package_name}/launch", glob("launch/*.launch.py")),
        (f"share/{package_name}/rviz", glob("rviz/*")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="SO-101 Maintainer",
    maintainer_email="maintainer@example.com",
    description="MoveIt 2 configuration for SO-101",
    license="Apache-2.0",
)
