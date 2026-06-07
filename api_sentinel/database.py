import sqlite3
from typing import Any, Dict, List, Optional
from api_sentinel.models import TestRunResult, CheckResult

def get_connection(db_path: str = "api_sentinel.db") -> sqlite3.Connection:
    """Returns a connection to the SQLite database with row factory set to dict."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# TODO: Introduce a DatabaseManager lifecycle class to handle database initialization once instead of calling init_db before every operation.
def init_db(db_path: str = "api_sentinel.db") -> None:
    """Initializes the database schema if it doesn't already exist."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # Enable foreign key support
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        # Create test_runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL,
                total_checks INTEGER NOT NULL,
                passed_checks INTEGER NOT NULL,
                failed_checks INTEGER NOT NULL,
                average_response_time_ms REAL NOT NULL
            );
        """)
        
        # Create check_results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS check_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                check_name TEXT NOT NULL,
                method TEXT NOT NULL,
                url TEXT NOT NULL,
                expected_status INTEGER NOT NULL,
                actual_status INTEGER,
                response_time_ms REAL NOT NULL,
                passed INTEGER NOT NULL,
                error_message TEXT,
                FOREIGN KEY (run_id) REFERENCES test_runs(id) ON DELETE CASCADE
            );
        """)
        conn.commit()

def save_run(run_result: TestRunResult, db_path: str = "api_sentinel.db") -> int:
    """
    Saves a TestRunResult and its associated CheckResults to the database.
    
    Returns:
        The ID of the newly created test run.
    """
    init_db(db_path) # Safe check
    
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # Insert test run
        cursor.execute("""
            INSERT INTO test_runs (
                project_name, started_at, finished_at, total_checks, 
                passed_checks, failed_checks, average_response_time_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            run_result.project_name,
            run_result.started_at,
            run_result.finished_at,
            run_result.total_checks,
            run_result.passed_checks,
            run_result.failed_checks,
            run_result.average_response_time_ms
        ))
        
        run_id = cursor.lastrowid
        assert run_id is not None
        
        # Insert check results
        for result in run_result.results:
            cursor.execute("""
                INSERT INTO check_results (
                    run_id, check_name, method, url, expected_status, 
                    actual_status, response_time_ms, passed, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                result.name,
                result.method,
                result.url,
                result.expected_status,
                result.actual_status,
                result.response_time_ms,
                1 if result.passed else 0,
                result.error_message
            ))
            
        conn.commit()
        return run_id

def get_history(db_path: str = "api_sentinel.db") -> List[Dict[str, Any]]:
    """Retrieves all test runs ordered by ID descending."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM test_runs ORDER BY id DESC")
        return [dict(row) for row in cursor.fetchall()]

def get_run(run_id: int, db_path: str = "api_sentinel.db") -> Optional[Dict[str, Any]]:
    """Retrieves details of a specific test run."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM test_runs WHERE id = ?", (run_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_check_results(run_id: int, db_path: str = "api_sentinel.db") -> List[Dict[str, Any]]:
    """Retrieves all individual check results associated with a run ID."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM check_results WHERE run_id = ?", (run_id,))
        return [dict(row) for row in cursor.fetchall()]
