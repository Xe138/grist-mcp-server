#!/usr/bin/env python3
"""Rich test runner with progress display and fail-fast behavior.

Runs unit tests, then integration tests with real-time progress indication.
"""

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text


class Status(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"


@dataclass
class TestStage:
    name: str
    command: list[str]
    status: Status = Status.PENDING
    progress: int = 0
    total: int = 0
    passed: int = 0
    failed: int = 0
    current_test: str = ""
    duration: float = 0.0
    output: list[str] = field(default_factory=list)


# Regex patterns for parsing pytest output
PYTEST_PROGRESS = re.compile(r"\[\s*(\d+)%\]")
PYTEST_COLLECTING = re.compile(r"collected (\d+) items?")
PYTEST_RESULT = re.compile(r"(\d+) passed")
PYTEST_FAILED = re.compile(r"(\d+) failed")
PYTEST_DURATION = re.compile(r"in ([\d.]+)s")
PYTEST_TEST_LINE = re.compile(r"(tests/\S+::\S+)")


class TestRunner:
    def __init__(self, verbose: bool = False):
        self.console = Console()
        self.verbose = verbose
        self.project_root = Path(__file__).parent.parent
        self.stages: list[TestStage] = []
        self.all_passed = True

    def add_stage(self, name: str, command: list[str]) -> None:
        self.stages.append(TestStage(name=name, command=command))

    def render_table(self) -> Table:
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Status", width=3)
        table.add_column("Name", width=20)
        table.add_column("Progress", width=30)
        table.add_column("Time", width=8)

        for stage in self.stages:
            # Status icon
            if stage.status == Status.PENDING:
                icon = Text("○", style="dim")
            elif stage.status == Status.RUNNING:
                icon = Text("●", style="yellow")
            elif stage.status == Status.PASSED:
                icon = Text("✓", style="green")
            else:
                icon = Text("✗", style="red")

            # Progress display
            if stage.status == Status.PENDING:
                progress = Text("pending", style="dim")
            elif stage.status == Status.RUNNING:
                if stage.total > 0:
                    bar_width = 20
                    filled = int(bar_width * stage.progress / 100)
                    bar = "━" * filled + "░" * (bar_width - filled)
                    progress = Text(f"{bar} {stage.progress:3d}%  {stage.passed}/{stage.total}")
                    if stage.current_test:
                        progress.append(f"\n      → {stage.current_test[:40]}", style="dim")
                else:
                    progress = Text("collecting...", style="yellow")
            elif stage.status == Status.PASSED:
                progress = Text(f"{stage.passed}/{stage.total}", style="green")
            else:
                progress = Text(f"{stage.passed}/{stage.total} ({stage.failed} failed)", style="red")

            # Duration
            if stage.duration > 0:
                duration = Text(f"{stage.duration:.1f}s", style="dim")
            else:
                duration = Text("")

            table.add_row(icon, stage.name, progress, duration)

        return table

    def parse_output(self, stage: TestStage, line: str) -> None:
        """Parse pytest output line and update stage state."""
        stage.output.append(line)

        # Check for collected count
        match = PYTEST_COLLECTING.search(line)
        if match:
            stage.total = int(match.group(1))

        # Check for progress percentage
        match = PYTEST_PROGRESS.search(line)
        if match:
            stage.progress = int(match.group(1))
            # Estimate passed based on progress
            if stage.total > 0:
                stage.passed = int(stage.total * stage.progress / 100)

        # Check for current test
        match = PYTEST_TEST_LINE.search(line)
        if match:
            stage.current_test = match.group(1)

        # Check for final results
        match = PYTEST_RESULT.search(line)
        if match:
            stage.passed = int(match.group(1))

        match = PYTEST_FAILED.search(line)
        if match:
            stage.failed = int(match.group(1))

        match = PYTEST_DURATION.search(line)
        if match:
            stage.duration = float(match.group(1))

    def run_stage(self, stage: TestStage, live: Live) -> bool:
        """Run a single test stage and return True if passed."""
        stage.status = Status.RUNNING
        live.update(self.render_table())

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        try:
            process = subprocess.Popen(
                stage.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self.project_root,
                env=env,
            )

            for line in process.stdout:
                line = line.rstrip()
                self.parse_output(stage, line)
                live.update(self.render_table())

                if self.verbose:
                    self.console.print(line)

            process.wait()

            if process.returncode == 0:
                stage.status = Status.PASSED
                stage.progress = 100
                return True
            else:
                stage.status = Status.FAILED
                self.all_passed = False
                return False

        except Exception as e:
            stage.status = Status.FAILED
            stage.output.append(str(e))
            self.all_passed = False
            return False
        finally:
            live.update(self.render_table())

    def run_all(self) -> bool:
        """Run all test stages with fail-fast behavior."""
        self.console.print()

        with Live(self.render_table(), console=self.console, refresh_per_second=4) as live:
            for stage in self.stages:
                if not self.run_stage(stage, live):
                    # Fail fast - don't run remaining stages
                    break

        self.console.print()

        # Print summary
        if self.all_passed:
            self.console.print("[green]All tests passed![/green]")
        else:
            self.console.print("[red]Tests failed![/red]")
            # Print failure details
            for stage in self.stages:
                if stage.status == Status.FAILED:
                    self.console.print(f"\n[red]Failures in {stage.name}:[/red]")
                    # Print last 20 lines of output for context
                    for line in stage.output[-20:]:
                        self.console.print(f"  {line}")

        return self.all_passed


def main():
    parser = argparse.ArgumentParser(description="Run tests with rich progress display")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show full test output")
    parser.add_argument("--unit-only", action="store_true", help="Run only unit tests")
    parser.add_argument("--integration-only", action="store_true", help="Run only integration tests")
    args = parser.parse_args()

    runner = TestRunner(verbose=args.verbose)

    # Determine which stages to run
    run_unit = not args.integration_only
    run_integration = not args.unit_only

    if run_unit:
        runner.add_stage(
            "Unit Tests",
            ["uv", "run", "pytest", "tests/unit/", "-v", "--tb=short"],
        )

    if run_integration:
        # Use the integration test script which handles containers
        runner.add_stage(
            "Integration Tests",
            ["bash", "./scripts/run-integration-tests.sh"],
        )

    success = runner.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
