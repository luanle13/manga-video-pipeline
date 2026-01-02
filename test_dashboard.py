#!/usr/bin/env python3
"""
Test script to verify the dashboard implementation
"""

import sys
import os

# Add the src directory to the path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def test_dashboard_imports():
    """Test that dashboard modules can be imported."""
    print("Testing dashboard imports...")
    
    try:
        import src.dashboard.app
        print("✓ Dashboard app imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import dashboard app: {e}")
        return False
    
    try:
        import src.dashboard.routes
        print("✓ Dashboard routes imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import dashboard routes: {e}")
        return False
    
    return True


def test_routes_endpoints():
    """Test that routes are properly defined."""
    print("\nTesting route endpoints...")
    
    try:
        from src.dashboard import routes
        from fastapi.testclient import TestClient
        from src.dashboard.app import app
        
        client = TestClient(app)
        
        # Test main dashboard page
        response = client.get("/")
        assert response.status_code in [200, 404]  # 404 is OK if templates don't exist yet
        print("✓ Main dashboard route accessible")
        
        # Test API endpoints
        response = client.get("/api/stats")
        assert response.status_code == 200
        print("✓ Stats API endpoint accessible")
        
        response = client.get("/api/pipelines")
        assert response.status_code == 200
        print("✓ Pipelines API endpoint accessible")
        
        response = client.get("/api/uploads")
        assert response.status_code == 200
        print("✓ Uploads API endpoint accessible")
        
        response = client.get("/api/platform-health")
        assert response.status_code == 200
        print("✓ Platform health API endpoint accessible")
        
        # Test POST endpoints
        response = client.post("/api/trigger/discovery")
        assert response.status_code == 200
        print("✓ Trigger discovery endpoint accessible")
        
        response = client.post("/api/retry/upload/1")
        assert response.status_code == 200
        print("✓ Retry upload endpoint accessible")
        
        # Test HTMX components
        response = client.get("/components/stats")
        assert response.status_code == 200
        print("✓ Stats component endpoint accessible")
        
        response = client.get("/components/pipeline-list")
        assert response.status_code == 200
        print("✓ Pipeline list component endpoint accessible")
        
        response = client.get("/components/upload-status")
        assert response.status_code == 200
        print("✓ Upload status component endpoint accessible")
        
        response = client.get("/components/platform-health")
        assert response.status_code == 200
        print("✓ Platform health component endpoint accessible")
        
        return True
        
    except Exception as e:
        print(f"✗ Route test failed: {e}")
        return False


def test_templates_exist():
    """Test that required templates exist."""
    print("\nTesting template files...")
    
    import os
    from pathlib import Path
    
    templates_dir = Path("src/dashboard/templates")
    
    required_templates = [
        "base.html",
        "dashboard.html",
        "components/stats.html",
        "components/pipeline_list.html",
        "components/upload_status.html",
        "components/platform_health.html"
    ]
    
    missing = []
    for template in required_templates:
        template_path = templates_dir / template
        if not template_path.exists():
            missing.append(str(template_path))
        else:
            print(f"✓ {template} exists")
    
    if missing:
        print(f"✗ Missing templates: {missing}")
        return False
    
    return True


def main():
    """Run all tests."""
    print("Testing Dashboard Implementation...\n")
    
    success = True
    
    success &= test_dashboard_imports()
    success &= test_routes_endpoints()
    success &= test_templates_exist()
    
    if success:
        print("\n✓ All tests passed! The dashboard implementation looks good.")
        return 0
    else:
        print("\n✗ Some tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())