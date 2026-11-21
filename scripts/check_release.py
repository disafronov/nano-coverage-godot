"""Check Linux release-mode GDExtension binaries on the CI build baseline."""

import os
import re
import subprocess
from pathlib import Path

import utils


BIN_DIR = Path(utils.GODOT_PROJECT_DIR) / "addons/nano_coverage_godot/bin"
ABI_LIMITS = {
    "GLIBC": (2, 35),
    "GLIBCXX": (3, 4, 30),
    "CXXABI": (1, 3, 13),
}
TARGETS = ("editor", "template_debug")


def build_release_libraries():
    for target in TARGETS:
        subprocess.run(
            [
                "scons",
                "platform=linux",
                f"target={target}",
                "build_tests=no",
                "cache_path=.scons_cache/",
            ],
            cwd=utils.BUILD_DIR,
            check=True,
        )


def check_abi():
    for target in TARGETS:
        binary = BIN_DIR / f"nano_coverage_godot.linux.{target}.x86_64.so"
        if not binary.is_file():
            raise RuntimeError(f"Missing release binary: {binary}")

        version_info = subprocess.check_output(
            ["readelf", "--version-info", str(binary)], text=True
        )
        for family, limit in ABI_LIMITS.items():
            requirements = [
                tuple(map(int, version.split(".")))
                for version in re.findall(
                    rf"\\b{family}_(\\d+(?:\\.\\d+)+)\\b", version_info
                )
            ]
            highest = max(requirements, default=None)
            print(f"{binary.name}: {family} requires {highest}; limit {limit}")
            if highest is not None and highest > limit:
                raise RuntimeError(
                    f"{binary.name} requires {family}_{'.'.join(map(str, highest))}"
                )


def check_loading():
    godot = utils.find_godot_executable()
    if not godot:
        raise RuntimeError("Godot executable not found")

    script = Path(utils.GODOT_PROJECT_DIR) / "nano_release_smoke_ci.gd"
    script.write_text(
        """extends SceneTree

func _initialize() -> void:
    if not ClassDB.class_exists("CoverageApi"):
        push_error("Release GDExtension did not register CoverageApi")
        quit(1)
        return
    var api: Object = ClassDB.instantiate("CoverageApi")
    if api == null:
        push_error("Could not instantiate CoverageApi")
        quit(1)
        return
    print("Release GDExtension loaded successfully")
    quit(0)
""",
        encoding="utf-8",
    )
    try:
        subprocess.run(
            [
                godot,
                "--headless",
                "--path",
                utils.GODOT_PROJECT_DIR,
                "--script",
                "res://nano_release_smoke_ci.gd",
            ],
            check=True,
        )
    finally:
        script.unlink(missing_ok=True)


if __name__ == "__main__":
    build_release_libraries()
    check_abi()
    check_loading()
