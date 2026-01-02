#!/usr/bin/env python3
"""
Test suite runner for the manga video pipeline.
This script verifies that all test modules can be imported and run successfully.
"""

import sys
import os
import pytest
from pathlib import Path


def main():
    """Run the test suite."""
    print("Testing manga video pipeline test suite...")
    
    # Get the project root directory
    project_root = Path(__file__).parent
    tests_dir = project_root / "tests"
    
    # Check that all test directories exist
    required_dirs = [
        "test_discovery",
        "test_scraper", 
        "test_ai",
        "test_video",
        "test_uploader",
        "test_pipeline"
    ]
    
    for dir_name in required_dirs:
        dir_path = tests_dir / dir_name
        if not dir_path.exists():
            print(f"✗ Missing test directory: {dir_name}")
            return 1
        else:
            print(f"✓ Found test directory: {dir_name}")
    
    # Check that required test files exist
    required_test_files = [
        "test_discovery/test_mangadex.py",
        "test_discovery/test_manager.py",
        "test_scraper/test_mangadex.py", 
        "test_scraper/test_manager.py",
        "test_ai/test_summarizer.py",
        "test_ai/test_tts.py",
        "test_video/test_generator.py",
        "test_uploader/test_manager.py",
        "test_pipeline/test_workflow.py"
    ]
    
    for file_path in required_test_files:
        full_path = tests_dir / file_path
        if not full_path.exists():
            print(f"✗ Missing test file: {file_path}")
            return 1
        else:
            print(f"✓ Found test file: {file_path}")
    
    # Run the full test suite
    print("\nRunning full test suite...")
    test_result = pytest.main([
        str(tests_dir),
        "-v",  # Verbose output
        "--tb=short",  # Short traceback
        "-x",  # Stop on first failure
        "--disable-warnings"  # Suppress warnings
    ])
    
    if test_result == 0:
        print("\n✓ All tests passed successfully!")
        return 0
    else:
        print(f"\n✗ Tests failed with exit code: {test_result}")
        return test_result


if __name__ == "__main__":
    sys.exit(main())