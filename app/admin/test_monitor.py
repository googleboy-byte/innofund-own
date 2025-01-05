import unittest
import sys
import io
from datetime import datetime
from threading import Thread
import time
from flask import current_app
from app import db
from app.models import TestResult

class TestMonitor:
    @staticmethod
    def run_tests():
        """Run all tests and store results"""
        # Create string buffer to capture test output
        buffer = io.StringIO()
        runner = unittest.TextTestRunner(stream=buffer, verbosity=2)
        
        # Discover and load all tests from the tests directory
        loader = unittest.TestLoader()
        tests = loader.discover('tests', pattern='test_*.py')
        
        # Run tests and capture results
        start_time = datetime.utcnow()
        result = runner.run(tests)
        end_time = datetime.utcnow()
        
        # Parse results
        output = buffer.getvalue()
        success = result.wasSuccessful()
        total_tests = result.testsRun
        failures = len(result.failures)
        errors = len(result.errors)
        
        # Store results in database
        test_result = TestResult(
            timestamp=start_time,
            duration=(end_time - start_time).total_seconds(),
            success=success,
            total_tests=total_tests,
            failures=failures,
            errors=errors,
            output=output
        )
        
        try:
            db.session.add(test_result)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Error storing test results: {str(e)}")
            db.session.rollback()
        
        return test_result

    @staticmethod
    def get_latest_results(limit=10):
        """Get the latest test results"""
        return TestResult.query.order_by(TestResult.timestamp.desc()).limit(limit).all()

    @staticmethod
    def start_monitoring(interval=300):  # 5 minutes default
        """Start periodic test monitoring"""
        def monitor():
            while True:
                try:
                    TestMonitor.run_tests()
                except Exception as e:
                    current_app.logger.error(f"Error in test monitoring: {str(e)}")
                time.sleep(interval)
        
        thread = Thread(target=monitor, daemon=True)
        thread.start()
        return thread 