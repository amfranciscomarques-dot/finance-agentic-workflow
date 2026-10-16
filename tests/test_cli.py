from __future__ import annotations

from finance_workflow.cli import main
from finance_workflow.results import save_result
from finance_workflow.workflow import WorkflowResult


def test_cli_rejects_invalid_input_without_a_traceback(capsys):
    code = main(["run", "equity-research", "--ticker", "../AAPL", "--offline", "--no-save"])
    assert code == 2
    stderr = capsys.readouterr().err
    assert "Invalid ticker" in stderr
    assert "Traceback" not in stderr


def test_cli_handles_missing_holdings(capsys):
    assert main(["run", "portfolio", "--offline"]) == 2
    assert "--holdings is required" in capsys.readouterr().err


def test_cli_saves_a_report_to_an_explicit_path(tmp_path):
    path = tmp_path / "nested" / "memo.md"
    assert (
        main(["run", "equity-research", "--ticker", "AAPL", "--offline", "--output", str(path)])
        == 0
    )
    assert "Apple" in path.read_text()


def test_automatic_saving_keeps_successive_reports(tmp_path):
    result = WorkflowResult(workflow="monitor", params={}, markdown="# First")
    first = save_result(result, tmp_path)
    result.markdown = "# Second"
    second = save_result(result, tmp_path)
    assert first != second
    assert first.read_text() == "# First"
    assert second.read_text() == "# Second"
