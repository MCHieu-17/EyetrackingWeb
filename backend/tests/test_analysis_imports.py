"""Import contract cho package `app.services.analysis`."""

from app.services import analysis
from app.services.analysis import (
    execute_pending_runs,
    execute_run,
    export_lines,
    get_run_result,
    rebuild_course,
)


def test_analysis_package_exports_public_api():
    assert callable(analysis.execute_run)
    assert callable(analysis.get_run_result)
    assert callable(analysis.rebuild_course)
    assert callable(analysis.execute_pending_runs)
    assert callable(analysis.export_lines)


def test_analysis_direct_imports_match_package_exports():
    assert execute_run is analysis.execute_run
    assert get_run_result is analysis.get_run_result
    assert rebuild_course is analysis.rebuild_course
    assert execute_pending_runs is analysis.execute_pending_runs
    assert export_lines is analysis.export_lines
