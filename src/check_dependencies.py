"""Check the selected Python environment against the app's requirements."""

import sys
from importlib import metadata
from pathlib import Path


def dependency_problems(requirements_path: Path) -> list[str]:
    """Return actionable missing/version errors without importing app packages."""
    try:
        from packaging.requirements import InvalidRequirement, Requirement
        from packaging.version import InvalidVersion, Version
    except ImportError:
        return ["Missing packaging, which is required to check installed dependency versions."]

    problems = []
    for line_number, line in enumerate(requirements_path.read_text().splitlines(), 1):
        line = line.split(" #", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        try:
            requirement = Requirement(line)
        except InvalidRequirement:
            problems.append(f"Invalid requirement on line {line_number}: {line}")
            continue
        if requirement.marker and not requirement.marker.evaluate():
            continue
        try:
            installed = metadata.version(requirement.name)
        except metadata.PackageNotFoundError:
            problems.append(f"Missing {requirement.name}; requires {requirement.specifier or 'an installed version'}.")
            continue
        try:
            compatible = requirement.specifier.contains(Version(installed))
        except InvalidVersion:
            compatible = False
        if not compatible:
            problems.append(f"{requirement.name} {installed} is installed; requires {requirement.specifier}.")
    return problems


def main() -> int:
    requirements_path = Path(__file__).with_name("requirements.txt")
    try:
        problems = dependency_problems(requirements_path)
    except OSError as error:
        print(f"Cannot read dependency requirements: {error}", file=sys.stderr)
        return 1
    if problems:
        print("This Python environment needs dependency updates:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
