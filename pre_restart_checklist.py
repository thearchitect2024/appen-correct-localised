#!/usr/bin/env python3
"""
Pre-Restart Safety Checklist for AppenCorrect

This script validates all configurations and dependencies before restarting
the application with Redis cache and increased workers.
"""

import os
import sys
import subprocess
import socket
import time
from pathlib import Path

def print_header(title):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_status(check, status, message):
    """Print formatted status message."""
    icon = "✅" if status else "❌"
    print(f"{icon} {check}: {message}")
    return status

def check_files_exist():
    """Check if all required files exist."""
    print_header("FILE EXISTENCE CHECK")
    
    required_files = [
        ('.env', True),
        ('app.py', True), 
        ('cache_client.py', True),
        ('core.py', True),
        ('api_auth.py', True),
        ('requirements.txt', True),
        ('start_server.sh', False),
        ('start_gunicorn.sh', False),
        ('test_cache.py', False)
    ]
    
    all_good = True
    for file_path, critical in required_files:
        exists = Path(file_path).exists()
        status = "EXISTS" if exists else "MISSING"
        severity = "CRITICAL" if critical and not exists else "OK"
        
        if critical and not exists:
            all_good = False
            print_status(f"File {file_path}", False, f"{status} - {severity}")
        else:
            print_status(f"File {file_path}", exists, f"{status}")
    
    return all_good

def check_environment_config():
    """Check environment configuration."""
    print_header("ENVIRONMENT CONFIGURATION CHECK")
    
    # Load .env file manually
    env_vars = {}
    try:
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
    except FileNotFoundError:
        print_status("Environment file", False, ".env file not found")
        return False
    
    # Check critical variables
    checks = [
        ('VALKEY_HOST', 'Cache host configuration'),
        ('VALKEY_PORT', 'Cache port configuration'), 
        ('VALKEY_DB', 'Cache database configuration'),
        ('VALKEY_ENABLED', 'Cache enable flag'),
        ('WORKERS', 'Worker count configuration'),
        ('GEMINI_API_KEY', 'Gemini API key')
    ]
    
    all_good = True
    for var, description in checks:
        value = env_vars.get(var, os.getenv(var))
        if value and value != 'your_gemini_api_key_here':
            print_status(description, True, f"{var}={value}")
        else:
            print_status(description, False, f"{var} not set or using placeholder")
            if var in ['VALKEY_HOST', 'GEMINI_API_KEY']:
                all_good = False
    
    # Validate specific values
    if env_vars.get('VALKEY_ENABLED', '').lower() == 'true':
        if not env_vars.get('VALKEY_HOST'):
            print_status("Cache configuration", False, "VALKEY_ENABLED=true but no VALKEY_HOST")
            all_good = False
        else:
            print_status("Cache configuration", True, "Properly configured")
    
    return all_good

def check_network_connectivity():
    """Check network connectivity to Valkey/Redis."""
    print_header("NETWORK CONNECTIVITY CHECK")
    
    # Load Valkey host from environment
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('VALKEY_HOST='):
                    host = line.split('=', 1)[1].strip()
                    break
            else:
                host = 'autoai-correct-0g4w6b.serverless.usw2.cache.amazonaws.com'
    except:
        host = 'autoai-correct-0g4w6b.serverless.usw2.cache.amazonaws.com'
    
    port = 6379
    
    print(f"Testing connection to {host}:{port}")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print_status("Network connectivity", True, f"Can reach {host}:{port}")
            return True
        else:
            print_status("Network connectivity", False, f"Cannot reach {host}:{port}")
            return False
    except Exception as e:
        print_status("Network connectivity", False, f"Connection test failed: {e}")
        return False

def check_python_dependencies():
    """Check if required Python packages are installed."""
    print_header("PYTHON DEPENDENCIES CHECK")
    
    required_packages = [
        ('flask', True),
        ('redis', False),  
        ('valkey', False),  # At least one of redis/valkey needed
        ('waitress', False),
        ('gunicorn', False),  # At least one server needed
        ('python-dotenv', True)
    ]
    
    all_good = True
    redis_available = False
    server_available = False
    
    for package, critical in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print_status(f"Package {package}", True, "INSTALLED")
            if package in ['redis', 'valkey']:
                redis_available = True
            if package in ['waitress', 'gunicorn']:
                server_available = True
        except ImportError:
            print_status(f"Package {package}", False, "NOT INSTALLED")
            if critical:
                all_good = False
    
    # Check if at least one cache client is available
    if not redis_available:
        print_status("Cache client", False, "Neither redis nor valkey package installed")
        print("  Install with: pip install redis valkey")
        all_good = False
    else:
        print_status("Cache client", True, "Redis/Valkey package available")
    
    # Check if at least one server is available
    if not server_available:
        print_status("WSGI server", False, "Neither waitress nor gunicorn installed")
        all_good = False
    else:
        print_status("WSGI server", True, "Server package available")
    
    return all_good

def test_cache_connection():
    """Test actual cache connection."""
    print_header("CACHE CONNECTION TEST")
    
    try:
        # Try to import and test cache
        sys.path.insert(0, '.')
        from cache_client import get_cache
        
        cache = get_cache()
        print_status("Cache client creation", True, "Cache client created successfully")
        
        if cache.is_available():
            print_status("Cache connectivity", True, "Cache is available and connected")
            
            # Test basic operations
            test_key = "pre_restart_test"
            test_value = {"test": True, "timestamp": time.time()}
            
            # Test SET
            if cache.set("test", test_key, test_value, ttl=60):
                print_status("Cache SET operation", True, "SET operation successful")
                
                # Test GET
                retrieved = cache.get("test", test_key)
                if retrieved == test_value:
                    print_status("Cache GET operation", True, "GET operation successful")
                    
                    # Test DELETE
                    cache.delete("test", test_key)
                    if cache.get("test", test_key) is None:
                        print_status("Cache DELETE operation", True, "DELETE operation successful")
                        return True
                    else:
                        print_status("Cache DELETE operation", False, "DELETE operation failed")
                else:
                    print_status("Cache GET operation", False, "Retrieved value doesn't match")
            else:
                print_status("Cache SET operation", False, "SET operation failed")
        else:
            print_status("Cache connectivity", False, "Cache not available")
    
    except ImportError as e:
        print_status("Cache client import", False, f"Cannot import cache_client: {e}")
    except Exception as e:
        print_status("Cache connection test", False, f"Test failed: {e}")
    
    return False

def check_current_app_status():
    """Check if the app is currently running and get its PID."""
    print_header("CURRENT APPLICATION STATUS")
    
    try:
        # Look for current AppenCorrect processes
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        processes = []
        
        for line in result.stdout.split('\n'):
            if 'app:app' in line or 'app.py' in line:
                if 'AppenCorrect' in line or '5006' in line:
                    processes.append(line.strip())
        
        if processes:
            print_status("Current app status", True, f"Found {len(processes)} running process(es)")
            for i, proc in enumerate(processes, 1):
                parts = proc.split()
                pid = parts[1] if len(parts) > 1 else "unknown"
                print(f"  Process {i}: PID {pid}")
                print(f"    Command: {' '.join(parts[10:])[:80]}...")
            
            # Get memory usage
            try:
                total_mem = 0
                for proc in processes:
                    parts = proc.split()
                    if len(parts) > 5:
                        mem_kb = int(parts[5])  # RSS in KB
                        total_mem += mem_kb
                
                print_status("Current memory usage", True, f"~{total_mem/1024:.1f}MB total")
            except:
                print_status("Memory usage", False, "Could not determine memory usage")
            
            return processes
        else:
            print_status("Current app status", True, "No AppenCorrect processes found (safe to start)")
            return []
            
    except Exception as e:
        print_status("Process check", False, f"Could not check processes: {e}")
        return None

def generate_restart_commands():
    """Generate safe restart commands."""
    print_header("RESTART COMMANDS")
    
    processes = check_current_app_status()
    
    print("\n📋 SAFE RESTART PROCEDURE:")
    print("\n1. STOP current processes (if any):")
    if processes:
        for proc in processes:
            parts = proc.split()
            if len(parts) > 1:
                pid = parts[1]
                print(f"   kill {pid}")
        print("   # Wait 5 seconds for graceful shutdown")
        print("   sleep 5")
    else:
        print("   # No processes to stop")
    
    print("\n2. INSTALL dependencies (if needed):")
    print("   pip install redis valkey")
    
    print("\n3. TEST cache connection:")
    print("   python3 test_cache.py")
    
    print("\n4. START with new configuration:")
    print("   # Option A: Waitress (recommended)")
    print("   ./start_server.sh")
    print("   # OR Option B: Gunicorn")  
    print("   ./start_gunicorn.sh")
    print("   # OR Option C: Manual")
    print("   waitress-serve --host=0.0.0.0 --port=5006 --threads=20 app:app")
    
    print("\n5. VERIFY startup:")
    print("   curl http://localhost:5006/health")
    print("   # Should return JSON with status info")

def main():
    """Run all checks."""
    print("AppenCorrect Pre-Restart Safety Checklist")
    print("This script will verify everything is ready before restart.")
    
    checks = [
        ("Files", check_files_exist),
        ("Environment", check_environment_config), 
        ("Network", check_network_connectivity),
        ("Dependencies", check_python_dependencies),
        ("Cache", test_cache_connection),
    ]
    
    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print_status(f"{name} check", False, f"Check failed with error: {e}")
            results[name] = False
    
    # Summary
    print_header("SUMMARY")
    
    all_passed = all(results.values())
    failed_checks = [name for name, result in results.items() if not result]
    
    if all_passed:
        print("🎉 ALL CHECKS PASSED! Safe to restart the application.")
        generate_restart_commands()
        return 0
    else:
        print(f"❌ {len(failed_checks)} check(s) failed: {', '.join(failed_checks)}")
        print("\n🔧 REQUIRED ACTIONS:")
        
        if "Files" in failed_checks:
            print("   - Create missing .env file from env.example")
        if "Environment" in failed_checks:
            print("   - Configure missing environment variables in .env")
        if "Network" in failed_checks:
            print("   - Check VPC/security group settings for ElastiCache access")
        if "Dependencies" in failed_checks:
            print("   - Install missing packages: pip install redis valkey")
        if "Cache" in failed_checks:
            print("   - Fix cache configuration and connectivity")
        
        print("\n⚠️ DO NOT RESTART until all checks pass!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
