import json
import os
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path

import pytest

from check_dependencies import dependency_problems


ROOT = Path(__file__).resolve().parents[1]
COMPATIBLE_VERSIONS = {
    "streamlit": "1.40.0",
    "pandas": "2.0.0",
    "requests": "2.31.0",
    "fastapi": "0.115.0",
    "pydantic": "2.0.0",
    "uvicorn": "0.35.0",
}


def installed_versions(monkeypatch, versions):
    def version(name):
        if name not in versions:
            raise metadata.PackageNotFoundError(name)
        return versions[name]

    monkeypatch.setattr("check_dependencies.metadata.version", version)


def test_preflight_accepts_all_current_requirements(monkeypatch):
    installed_versions(monkeypatch, COMPATIBLE_VERSIONS)
    assert dependency_problems(ROOT / "src/requirements.txt") == []


@pytest.mark.parametrize(
    ("package", "version"),
    [("streamlit", "1.30.0"), ("pandas", "4.0.0"), ("requests", "2.30.0"),
     ("fastapi", "0.100.0"), ("pydantic", "1.10.0"), ("uvicorn", "0.34.0")],
)
def test_preflight_rejects_installed_but_incompatible_packages(monkeypatch, package, version):
    installed_versions(monkeypatch, {**COMPATIBLE_VERSIONS, package: version})
    problems = dependency_problems(ROOT / "src/requirements.txt")
    assert len(problems) == 1
    assert package in problems[0] and version in problems[0]
    assert "requires" in problems[0]


def test_preflight_reports_every_missing_dependency(monkeypatch):
    installed_versions(monkeypatch, {})
    problems = dependency_problems(ROOT / "src/requirements.txt")
    assert len(problems) == len(COMPATIBLE_VERSIONS)
    assert all(any(f"Missing {name};" in issue for issue in problems) for name in COMPATIBLE_VERSIONS)


def test_preflight_handles_missing_packaging(monkeypatch):
    monkeypatch.setitem(sys.modules, "packaging.requirements", None)
    problems = dependency_problems(ROOT / "src/requirements.txt")
    assert len(problems) == 1
    assert "Missing packaging" in problems[0]


def test_preflight_observes_markers_comments_and_invalid_versions(monkeypatch, tmp_path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        '# Ignore comments and blank lines.\n\n'
        'not-for-this-python>=1; python_version < "2"\n'
        'pandas>=2,<4 # inline explanation\n'
    )
    installed_versions(monkeypatch, {"pandas": "unknown-version"})
    problems = dependency_problems(requirements)
    assert len(problems) == 1 and "pandas unknown-version" in problems[0]


@pytest.fixture
def launcher(tmp_path):
    if os.name == "nt":
        pytest.skip("The Bash process tests run on macOS/Linux; the shared preflight is platform independent.")
    project = tmp_path / "tablebeam project"
    (project / "src").mkdir(parents=True)
    for relative in ("start.sh", "src/check_dependencies.py", "src/requirements.txt"):
        shutil.copy2(ROOT / relative, project / relative)
    (project / "src/app.py").touch()
    environment = project / "env with spaces"
    (environment / "bin").mkdir(parents=True)
    # A relocated environment may retain an activation script pointing elsewhere.
    (environment / "bin/activate").write_text("echo 'stale activation used' >&2\nexit 99\n")
    interpreter = environment / "bin/python"
    interpreter.write_text(f"#!{sys.executable}\n" + '''
import json
import os
import shutil
import sys
from pathlib import Path

args = sys.argv[1:]
with open(os.environ["FAKE_CALL_LOG"], "a") as log:
    log.write(json.dumps({"interpreter": sys.argv[0], "args": args,
        "demo": os.environ.get("START_WITH_DEMO"),
        "provider": os.environ.get("LLM_PROVIDER"),
        "endpoint": os.environ.get("LLM_BASE_URL"),
        "start_server": os.environ.get("AUTO_START_PROVIDER")}) + "\\n")
ready = Path(os.environ["FAKE_READY"])
if args[0] == "-c":
    sys.exit(0)
if args[:2] == ["-m", "venv"]:
    executable = Path(args[2]) / "bin/python"
    executable.parent.mkdir(parents=True)
    shutil.copy2(sys.argv[0], executable)
    sys.exit(0)
if args == ["src/check_dependencies.py"]:
    if ready.exists():
        sys.exit(0)
    print("streamlit 1.30.0 is installed; requires <2,>=1.40.", file=sys.stderr)
    sys.exit(1)
if args[:2] == ["-m", "pip"]:
    if os.environ.get("FAKE_INSTALL_FAIL"):
        sys.exit(17)
    if not os.environ.get("FAKE_STILL_STALE"):
        ready.touch()
    sys.exit(0)
if args[:2] == ["-m", "streamlit"]:
    sys.exit(int(os.environ.get("FAKE_APP_EXIT", "0")))
raise SystemExit("Unexpected interpreter invocation: " + repr(args))
''')
    interpreter.chmod(0o755)
    call_log = project / "calls.jsonl"
    ready = project / "ready"
    base_env = {key: value for key, value in os.environ.items() if key not in {
        "LLM_PROVIDER", "LLM_BASE_URL", "START_WITH_DEMO", "AUTO_START_PROVIDER",
        "VENV_DIR", "PYTHON_BIN", "TABLEBEAM_PIP_VERBOSE",
    }}
    base_env.update({"VENV_DIR": str(environment), "PYTHON_BIN": "/no/ambient/python",
                     "FAKE_CALL_LOG": str(call_log), "FAKE_READY": str(ready)})

    def run(*arguments, **extra_env):
        result = subprocess.run(["bash", str(project / "start.sh"), *arguments],
                                cwd=tmp_path, env={**base_env, **extra_env},
                                text=True, capture_output=True, timeout=15)
        calls = [json.loads(line) for line in call_log.read_text().splitlines()] if call_log.exists() else []
        return result, calls

    return run, ready, interpreter, environment


def test_launcher_reuses_selected_environment_without_activation_or_install(launcher):
    run, ready, interpreter, _ = launcher
    ready.touch()
    result, calls = run("--skip-install", "--demo", "--ollama", "--start-server")
    assert result.returncode == 0, result.stderr
    assert len(calls) == 3
    assert all(Path(call["interpreter"]) == interpreter for call in calls)
    launch = calls[-1]
    assert launch["args"][:4] == ["-m", "streamlit", "run", "src/app.py"]
    assert launch["demo"] == "1" and launch["start_server"] == "1"
    assert launch["provider"] == "Ollama"
    assert launch["endpoint"] == "http://localhost:11434/v1"


def test_launcher_creates_new_environment_then_uses_its_interpreter(launcher):
    run, ready, base_interpreter, environment = launcher
    ready.touch()
    new_environment = environment.parent / "fresh environment"
    result, calls = run(PYTHON_BIN=str(base_interpreter), VENV_DIR=str(new_environment))
    assert result.returncode == 0, result.stderr
    assert calls[1]["args"] == ["-m", "venv", str(new_environment)]
    assert len(calls) == 5
    assert all(Path(call["interpreter"]) == new_environment / "bin/python" for call in calls[2:])


def test_skip_install_stops_incompatible_environment_before_app_launch(launcher):
    run, _, _, _ = launcher
    result, calls = run("--skip-install")
    assert result.returncode == 1
    assert "streamlit 1.30.0" in result.stderr
    assert "--skip-install prevents updates" in result.stderr
    assert len(calls) == 2


def test_launcher_installs_stale_dependencies_and_rechecks_before_launch(launcher):
    run, _, interpreter, _ = launcher
    result, calls = run(TABLEBEAM_PIP_VERBOSE="1")
    assert result.returncode == 0, result.stderr
    assert len(calls) == 5
    install = calls[2]["args"]
    assert install[:5] == ["-m", "pip", "install", "-r", "src/requirements.txt"]
    assert {"--default-timeout=30", "--retries=3", "--verbose", "--no-input"} <= set(install)
    assert calls[3]["args"] == ["src/check_dependencies.py"]
    assert calls[4]["args"][:2] == ["-m", "streamlit"]
    assert all(Path(call["interpreter"]) == interpreter for call in calls)


@pytest.mark.parametrize("failure", ["FAKE_INSTALL_FAIL", "FAKE_STILL_STALE"])
def test_launcher_does_not_launch_after_failed_dependency_repair(launcher, failure):
    run, _, _, _ = launcher
    result, calls = run(**{failure: "1"})
    assert result.returncode == 1
    assert not any(call["args"][:2] == ["-m", "streamlit"] for call in calls)
    if failure == "FAKE_INSTALL_FAIL":
        assert "TABLEBEAM_PIP_VERBOSE=1" in result.stderr
    else:
        assert "still incompatible after installation" in result.stderr


def test_launcher_preserves_incomplete_existing_environment(launcher):
    run, _, interpreter, environment = launcher
    interpreter.unlink()
    preserved = environment / "user-file.txt"
    preserved.write_text("keep this")
    result, calls = run()
    assert result.returncode == 1
    assert "no usable bin/python" in result.stderr
    assert "python3 -m venv" in result.stderr
    assert preserved.read_text() == "keep this"
    assert calls == []


def test_launcher_preserves_endpoint_override_and_app_exit_code(launcher):
    run, ready, _, _ = launcher
    ready.touch()
    result, calls = run("--ollama", LLM_BASE_URL="http://localhost:9876/v1", FAKE_APP_EXIT="7")
    assert result.returncode == 7
    assert calls[-1]["endpoint"] == "http://localhost:9876/v1"


def test_launcher_help_and_invalid_options_do_not_touch_environment(launcher):
    run, _, _, _ = launcher
    help_result, calls = run("--help")
    assert help_result.returncode == 0 and "Usage:" in help_result.stdout
    assert calls == []
    invalid_result, calls = run("--mystery")
    assert invalid_result.returncode == 2
    assert "Unknown option" in invalid_result.stderr
    assert calls == []
