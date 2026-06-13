import os
import json
import pytest
from typer.testing import CliRunner
from api_sentinel.cli import app
from api_sentinel.database import init_db, save_run
from api_sentinel.models import TestRunResult, CheckResult

runner = CliRunner()

def create_mock_run_result(project_name="Test Project", passed=True, name="Check 1", path="/v1/test", error_msg=None):
    return TestRunResult(
        project_name=project_name,
        started_at="2026-06-13T11:00:00Z",
        finished_at="2026-06-13T11:00:05Z",
        total_checks=1,
        passed_checks=1 if passed else 0,
        failed_checks=0 if passed else 1,
        average_response_time_ms=42.5,
        results=[
            CheckResult(
                name=name,
                method="GET",
                url=f"http://localhost{path}",
                expected_status=200,
                actual_status=200 if passed else 500,
                response_time_ms=42.5,
                passed=passed,
                valid_json=False,
                error_message=error_msg
            )
        ]
    )

def test_cli_export_html_success(tmp_path):
    db_file = tmp_path / "test.db"
    out_file = tmp_path / "report.html"
    
    init_db(str(db_file))
    mock_run = create_mock_run_result(project_name="HTML Success Project")
    save_run(mock_run, db_path=str(db_file))
    
    result = runner.invoke(app, [
        "export",
        "--run-id", "1",
        "--format", "html",
        "--output", str(out_file),
        "--db", str(db_file)
    ])
    
    assert result.exit_code == 0
    assert "Successfully exported HTML report" in result.output
    assert out_file.exists()
    
    html_content = out_file.read_text(encoding="utf-8")
    assert "HTML Success Project" in html_content
    assert "Run ID:</strong> #1" in html_content
    assert "Check 1" in html_content
    assert "/v1/test" in html_content
    assert "PASS" in html_content
    assert "42.5 ms" in html_content

def test_cli_export_html_escaping(tmp_path):
    db_file = tmp_path / "test.db"
    out_file = tmp_path / "report.html"
    
    init_db(str(db_file))
    # Create run with potentially unsafe HTML characters in user/config/runtime fields
    mock_run = create_mock_run_result(
        project_name="<script>alert('project')</script>",
        passed=False,
        name="Check <script>",
        path="/v1/test?q=<a>",
        error_msg="Error & <danger>"
    )
    save_run(mock_run, db_path=str(db_file))
    
    result = runner.invoke(app, [
        "export",
        "--run-id", "1",
        "--format", "html",
        "--output", str(out_file),
        "--db", str(db_file)
    ])
    
    assert result.exit_code == 0
    assert out_file.exists()
    
    html_content = out_file.read_text(encoding="utf-8")
    # Raw scripts should not exist in the HTML content
    assert "<script>" not in html_content
    assert "<a>" not in html_content
    assert "<danger>" not in html_content
    
    # Escaped versions should exist
    assert "&lt;script&gt;alert(&#x27;project&#x27;)&lt;/script&gt;" in html_content
    assert "Check &lt;script&gt;" in html_content
    assert "/v1/test?q=&lt;a&gt;" in html_content
    assert "Error &amp; &lt;danger&gt;" in html_content

def test_cli_export_missing_run_id(tmp_path):
    db_file = tmp_path / "test.db"
    init_db(str(db_file))
    
    result = runner.invoke(app, [
        "export",
        "--run-id", "999",
        "--format", "html",
        "--db", str(db_file)
    ])
    
    assert result.exit_code == 1
    assert "Error: Run with ID 999 not found in database." in result.output

def test_cli_export_invalid_format(tmp_path):
    db_file = tmp_path / "test.db"
    init_db(str(db_file))
    
    result = runner.invoke(app, [
        "export",
        "--run-id", "1",
        "--format", "yaml",
        "--db", str(db_file)
    ])
    
    assert result.exit_code == 1
    assert "Error: Unsupported format 'yaml'." in result.output

def test_cli_export_auto_create_dir(tmp_path):
    db_file = tmp_path / "test.db"
    out_file = tmp_path / "nested" / "dir" / "report.html"
    
    init_db(str(db_file))
    mock_run = create_mock_run_result()
    save_run(mock_run, db_path=str(db_file))
    
    result = runner.invoke(app, [
        "export",
        "--run-id", "1",
        "--format", "html",
        "--output", str(out_file),
        "--db", str(db_file)
    ])
    
    assert result.exit_code == 0
    assert out_file.exists()
    assert out_file.parent.exists()

def test_cli_export_json_output(tmp_path):
    db_file = tmp_path / "test.db"
    init_db(str(db_file))
    mock_run = create_mock_run_result(project_name="JSON Project")
    save_run(mock_run, db_path=str(db_file))
    
    # Test stdout print when --output is omitted for JSON
    result = runner.invoke(app, [
        "export",
        "--run-id", "1",
        "--format", "json",
        "--db", str(db_file)
    ])
    assert result.exit_code == 0
    exported_data = json.loads(result.output)
    assert exported_data["project_name"] == "JSON Project"
    assert exported_data["run_id"] == 1
    
    # Test file write when --output is provided for JSON
    out_file = tmp_path / "report.json"
    result_file = runner.invoke(app, [
        "export",
        "--run-id", "1",
        "--format", "json",
        "--output", str(out_file),
        "--db", str(db_file)
    ])
    assert result_file.exit_code == 0
    assert out_file.exists()
    file_data = json.loads(out_file.read_text(encoding="utf-8"))
    assert file_data["project_name"] == "JSON Project"

def test_cli_export_html_default_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db_file = "isolated.db"
    init_db(db_file)
    mock_run = create_mock_run_result(project_name="Default Path Project")
    save_run(mock_run, db_path=db_file)
    
    result = runner.invoke(app, [
        "export",
        "--run-id", "1",
        "--format", "html",
        "--db", db_file
    ])
    
    assert result.exit_code == 0
    expected_default_path = os.path.join("reports", "run-1.html")
    assert f"Successfully exported HTML report to {expected_default_path}" in result.output.replace("/", os.sep)
    assert os.path.exists(expected_default_path)
    
    html_content = open(expected_default_path, "r", encoding="utf-8").read()
    assert "Default Path Project" in html_content

def test_cli_run_concurrency_invalid(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text('{"project_name": "Test", "base_url": "http://localhost", "checks": []}', encoding="utf-8")
    
    result = runner.invoke(app, [
        "run",
        "--config", str(config_file),
        "--concurrency", "0",
        "--db", str(tmp_path / "test.db")
    ])
    assert result.exit_code == 1
    assert "concurrency must be at least 1" in result.output.lower()

def test_cli_run_concurrency_valid(tmp_path):
    from unittest.mock import MagicMock, patch
    config_file = tmp_path / "config.json"
    config_file.write_text('{"project_name": "Test", "base_url": "http://localhost", "checks": []}', encoding="utf-8")
    
    with patch("api_sentinel.cli.run_checks") as mock_run_checks:
        mock_run_checks.return_value = MagicMock(
            project_name="Test",
            started_at="2026-06-13T11:00:00Z",
            finished_at="2026-06-13T11:00:05Z",
            total_checks=0,
            passed_checks=0,
            failed_checks=0,
            average_response_time_ms=0.0,
            results=[]
        )
        
        result = runner.invoke(app, [
            "run",
            "--config", str(config_file),
            "--concurrency", "3",
            "--db", str(tmp_path / "test.db")
        ])
        assert result.exit_code == 0
        mock_run_checks.assert_called_once()
        assert mock_run_checks.call_args[1]["concurrency"] == 3
