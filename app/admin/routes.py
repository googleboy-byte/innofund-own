from flask import render_template, jsonify
from . import admin_bp
from .test_monitor import TestMonitor

@admin_bp.route('/tests')
def test_dashboard():
    """Display test monitoring dashboard"""
    return render_template('admin/test_dashboard.html')

@admin_bp.route('/api/test-results')
def get_test_results():
    """Get latest test results as JSON"""
    results = TestMonitor.get_latest_results()
    return jsonify([result.to_dict() for result in results])

@admin_bp.route('/api/run-tests', methods=['POST'])
def run_tests():
    """Manually trigger test run"""
    result = TestMonitor.run_tests()
    return jsonify(result.to_dict())

# Initialize test monitoring when the app starts
@admin_bp.before_app_first_request
def start_test_monitoring():
    TestMonitor.start_monitoring(interval=300)  # Run tests every 5 minutes 