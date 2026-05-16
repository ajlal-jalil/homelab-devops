"""
setup.py is the standard Pythong packaging file.
ament_python uses it to know how to instlal the package.
"""
from setuptools import find_packages, setup

# Package name - must match the directory and package.xml.
package_name = 'turtle_chase_py'

setup(
    name=package_name,
    version='0.1.0',
    # find_packages() discovers all directories with __init__.py.
    # We exclude 'test' so test code doesn't ship in the install.
    packages=find_packages(exclude=['test']),
    # data_files: non-Python files to install alongside the code.
    # The first tuple installs the resource marker so ROS sees the package.
    # The second installs package.xml.
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Jay',
    maintainer_email='ajlal.jalil@gmail.com',
    description='Python scenario test driver.',
    license='MIT',
    tests_require=['pytest'],
    # entry_points: this is how 'ros2 run turtle_chase_py scenario_runner'
    # finds the executable. It maps a script name to a Python function.
    entry_points={
        'console_scripts': [
            'scenario_runner = turtle_chase_py.scenario_runner:main',
        ],
    },
)
