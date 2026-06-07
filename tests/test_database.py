import os
import sqlite3
import pytest
from api_sentinel.models import TestRunResult, CheckResult
from api_sentinel.database import (
    init_db,
    save_run,
    get_history,
    get_run,
    get_check_results
)

def test_database_isolation_and_operations(tmp_path):
    # Setup isolated database path
    db_file = tmp_path / "test_isolated.db"
    db_path = str(db_file)
    
    # 1. Initialize schema
    init_db(db_path)
    assert db_file.exists()
    
    # Verify tables exist using raw sqlite
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    assert "test_runs" in tables
    assert "check_results" in tables

    # 2. Save a test run result
    mock_run_result = TestRunResult(
        project_name="Isolated API Test",
        started_at="2026-06-07T11:00:00Z",
        finished_at="2026-06-07T11:00:05Z",
        total_checks=2,
        passed_checks=1,
        failed_checks=1,
        average_response_time_ms=50.0,
        results=[
            CheckResult(
                name="Pass check",
                method="GET",
                url="http://localhost/health",
                expected_status=200,
                actual_status=200,
                response_time_ms=10.0,
                passed=True,
                valid_json=False
            ),
            CheckResult(
                name="Fail check",
                method="POST",
                url="http://localhost/users",
                expected_status=201,
                actual_status=500,
                response_time_ms=90.0,
                passed=False,
                valid_json=False,
                error_message="Expected status 201 but got 500"
            )
        ]
    )
    
    run_id = save_run(mock_run_result, db_path=db_path)
    assert run_id == 1

    # 3. Retrieve run details
    run_details = get_run(run_id, db_path=db_path)
    assert run_details is not None
    assert run_details["project_name"] == "Isolated API Test"
    assert run_details["total_checks"] == 2
    assert run_details["passed_checks"] == 1
    assert run_details["failed_checks"] == 1
    assert run_details["average_response_time_ms"] == 50.0

    # 4. Retrieve checks results
    check_records = get_check_results(run_id, db_path=db_path)
    assert len(check_records) == 2
    
    pass_record = next(c for c in check_records if c["check_name"] == "Pass check")
    assert pass_record["method"] == "GET"
    assert pass_record["passed"] == 1
    assert pass_record["actual_status"] == 200

    fail_record = next(c for c in check_records if c["check_name"] == "Fail check")
    assert fail_record["method"] == "POST"
    assert fail_record["passed"] == 0
    assert fail_record["actual_status"] == 500
    assert fail_record["error_message"] == "Expected status 201 but got 500"

    # 5. Retrieve history
    history = get_history(db_path=db_path)
    assert len(history) == 1
    assert history[0]["id"] == run_id
