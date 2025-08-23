#!/usr/bin/env python
"""
Test script to demonstrate the new proxy_command functionality.
This script tests both the new proxy_command approach and backward compatibility.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dpdispatcher.contexts.ssh_context import SSHSession

def test_new_proxy_command():
    """Test the new proxy_command approach."""
    print("Testing new proxy_command approach...")
    
    # Create an SSHSession with proxy_command (without actually connecting)
    try:
        # This will fail at the connection stage, but we can test parameter handling
        config = {
            'hostname': 'target.example.com',
            'username': 'user',
            'password': 'dummy',  # For test only
            'proxy_command': 'ssh -W %h:%p -i ~/.ssh/jump_key jumpuser@bastion.example.com'
        }
        
        # Create session but intercept before actual connection
        import paramiko
        original_proxy_command = paramiko.ProxyCommand
        
        captured_proxy_command = None
        def mock_proxy_command(command):
            global captured_proxy_command
            captured_proxy_command = command
            # Return a mock object to avoid actual connection
            class MockProxy:
                def settimeout(self, timeout): pass
                def close(self): pass
            return MockProxy()
        
        paramiko.ProxyCommand = mock_proxy_command
        
        try:
            session = SSHSession(**config)
        except:
            # Expected to fail at transport stage
            pass
        
        paramiko.ProxyCommand = original_proxy_command
        
        if captured_proxy_command:
            print(f"✓ Proxy command correctly set to: {captured_proxy_command}")
            return True
        else:
            print("✗ Proxy command was not captured")
            return False
            
    except Exception as e:
        print(f"✗ Error in proxy_command test: {e}")
        return False

def test_backward_compatibility():
    """Test backward compatibility with individual jump host parameters."""
    print("\nTesting backward compatibility...")
    
    try:
        config = {
            'hostname': 'target.example.com',
            'username': 'user',
            'password': 'dummy',  # For test only
            'jump_hostname': 'bastion.example.com',
            'jump_username': 'jumpuser',
            'jump_port': 2222,
            'jump_key_filename': '~/.ssh/jump_key'
        }
        
        # Create session but intercept before actual connection
        import paramiko
        original_proxy_command = paramiko.ProxyCommand
        
        captured_proxy_command = None
        def mock_proxy_command(command):
            global captured_proxy_command
            captured_proxy_command = command
            # Return a mock object to avoid actual connection
            class MockProxy:
                def settimeout(self, timeout): pass
                def close(self): pass
            return MockProxy()
        
        paramiko.ProxyCommand = mock_proxy_command
        
        try:
            session = SSHSession(**config)
        except:
            # Expected to fail at transport stage
            pass
        
        paramiko.ProxyCommand = original_proxy_command
        
        if captured_proxy_command:
            print(f"✓ Legacy parameters converted to proxy command: {captured_proxy_command}")
            expected_parts = ['-W', 'target.example.com:22', '-p', '2222', '-i', '~/.ssh/jump_key', 'jumpuser@bastion.example.com']
            all_parts_present = all(part in captured_proxy_command for part in expected_parts)
            if all_parts_present:
                print("✓ All expected parameters are present in the generated proxy command")
                return True
            else:
                print("✗ Some expected parameters are missing from the proxy command")
                return False
        else:
            print("✗ Proxy command was not captured")
            return False
            
    except Exception as e:
        print(f"✗ Error in backward compatibility test: {e}")
        return False

def test_conflict_detection():
    """Test that specifying both proxy_command and jump host parameters raises an error."""
    print("\nTesting conflict detection...")
    
    try:
        config = {
            'hostname': 'target.example.com',
            'username': 'user',
            'password': 'dummy',
            'proxy_command': 'ssh -W %h:%p jumpuser@bastion.example.com',
            'jump_hostname': 'bastion.example.com'  # This should cause a conflict
        }
        
        try:
            session = SSHSession(**config)
            print("✗ Expected ValueError was not raised")
            return False
        except ValueError as e:
            if "Cannot specify both" in str(e):
                print("✓ Conflict correctly detected and ValueError raised")
                return True
            else:
                print(f"✗ Wrong error message: {e}")
                return False
                
    except Exception as e:
        print(f"✗ Unexpected error in conflict test: {e}")
        return False

if __name__ == "__main__":
    print("Testing SSH Jump Host proxy_command functionality...")
    print("=" * 60)
    
    tests = [
        test_new_proxy_command,
        test_backward_compatibility,
        test_conflict_detection
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All tests passed! The proxy_command functionality is working correctly.")
        sys.exit(0)
    else:
        print("✗ Some tests failed.")
        sys.exit(1)