from setuptools import setup, find_packages

setup(
    name="smoke_alarm",
    version="1.0.0",
    description="Raspberry Pi cigarette-smoke detector with countermeasures",
    author="AlexanderHultsch",
    packages=find_packages(exclude=["tests*"]),
    python_requires=">=3.9",
    install_requires=[
        "requests>=2.28.0",
    ],
    entry_points={
        "console_scripts": [
            "smoke-alarm=smoke_alarm.main:main",
        ],
    },
)
