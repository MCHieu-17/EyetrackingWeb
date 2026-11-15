"""Import contract cho package `app.services.analysis`."""

from app.services import analysis


def test_analysis_package_exports_public_api():
    assert callable(analysis.analyze_lesson)
    assert callable(analysis.rebuild_course)
    assert callable(analysis.execute_pending_runs)
    assert callable(analysis.export_lines)
