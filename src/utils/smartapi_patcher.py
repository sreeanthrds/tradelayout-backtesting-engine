"""
SmartAPI Library Patcher
Fixes the hardcoded IP issue in SmartAPI library
"""

import os
import shutil
from pathlib import Path


def patch_smartapi_library():
    """
    Patch SmartAPI library to remove hardcoded IP.
    
    The SmartAPI library has a bug where it always sets clientPublicIp to
    "106.193.147.98" in the finally block, overriding the actual detected IP.
    
    This function comments out that line to use the actual detected IP.
    
    Returns:
        bool: True if patched successfully, False otherwise
    """
    try:
        # Find SmartAPI installation
        import SmartApi
        smartapi_path = Path(SmartApi.__file__).parent / 'smartConnect.py'
        
        if not smartapi_path.exists():
            print(f"❌ SmartAPI file not found at: {smartapi_path}")
            return False
        
        print(f"📍 Found SmartAPI at: {smartapi_path}")
        
        # Read the file
        with open(smartapi_path, 'r') as f:
            content = f.read()
        
        # Check if already patched
        if '# clientPublicIp="106.193.147.98"' in content or '# PATCHED' in content:
            print("✅ SmartAPI library already patched")
            return True
        
        # Check if the problematic line exists
        if 'clientPublicIp="106.193.147.98"' not in content:
            print("⚠️ Hardcoded IP line not found - library might be updated")
            return True
        
        # Create backup
        backup_path = smartapi_path.with_suffix('.py.backup')
        if not backup_path.exists():
            shutil.copy2(smartapi_path, backup_path)
            print(f"💾 Backup created at: {backup_path}")
        
        # Patch the file
        patched_content = content.replace(
            '        clientPublicIp="106.193.147.98"',
            '        # clientPublicIp="106.193.147.98"  # PATCHED: Use actual IP instead of hardcoded'
        )
        
        # Write patched content
        with open(smartapi_path, 'w') as f:
            f.write(patched_content)
        
        print("✅ SmartAPI library patched successfully!")
        print("   The library will now use your actual public IP")
        return True
        
    except Exception as e:
        print(f"❌ Error patching SmartAPI library: {e}")
        return False


def restore_smartapi_library():
    """
    Restore original SmartAPI library from backup.
    
    Returns:
        bool: True if restored successfully, False otherwise
    """
    try:
        import SmartApi
        smartapi_path = Path(SmartApi.__file__).parent / 'smartConnect.py'
        backup_path = smartapi_path.with_suffix('.py.backup')
        
        if not backup_path.exists():
            print("⚠️ No backup found")
            return False
        
        shutil.copy2(backup_path, smartapi_path)
        print("✅ SmartAPI library restored from backup")
        return True
        
    except Exception as e:
        print(f"❌ Error restoring SmartAPI library: {e}")
        return False


def check_smartapi_status():
    """
    Check if SmartAPI library is patched.
    
    Returns:
        dict: Status information
    """
    try:
        import SmartApi
        smartapi_path = Path(SmartApi.__file__).parent / 'smartConnect.py'
        backup_path = smartapi_path.with_suffix('.py.backup')
        
        with open(smartapi_path, 'r') as f:
            content = f.read()
        
        is_patched = '# PATCHED' in content or '# clientPublicIp="106.193.147.98"' in content
        has_backup = backup_path.exists()
        has_hardcoded_ip = 'clientPublicIp="106.193.147.98"' in content and '# PATCHED' not in content
        
        return {
            'path': str(smartapi_path),
            'is_patched': is_patched,
            'has_backup': has_backup,
            'has_hardcoded_ip': has_hardcoded_ip,
            'needs_patch': has_hardcoded_ip and not is_patched
        }
        
    except Exception as e:
        return {
            'error': str(e)
        }


if __name__ == "__main__":
    print("\n" + "="*80)
    print("SMARTAPI LIBRARY PATCHER")
    print("="*80)
    
    # Check status
    print("\n[STEP 1] Checking SmartAPI status...")
    status = check_smartapi_status()
    
    if 'error' in status:
        print(f"❌ Error: {status['error']}")
    else:
        print(f"   Path: {status['path']}")
        print(f"   Is Patched: {status['is_patched']}")
        print(f"   Has Backup: {status['has_backup']}")
        print(f"   Needs Patch: {status['needs_patch']}")
    
    # Patch if needed
    if status.get('needs_patch'):
        print("\n[STEP 2] Patching SmartAPI library...")
        if patch_smartapi_library():
            print("\n✅ SUCCESS! SmartAPI library patched")
            print("   The library will now use your actual public IP")
            print("   You can restore the original with restore_smartapi_library()")
        else:
            print("\n❌ FAILED to patch SmartAPI library")
    elif status.get('is_patched'):
        print("\n✅ SmartAPI library is already patched")
    
    print("\n" + "="*80)
