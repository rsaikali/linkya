#!/usr/bin/env python3
"""Script to remove type hints from Python files using strip-hints."""

from pathlib import Path
import subprocess


def process_file(file_path):
    """Process a single Python file to remove type hints."""
    try:
        # Use strip-hints to remove type annotations
        result = subprocess.run(
            ['strip-hints', str(file_path), '--to-empty'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            # Overwrite the file with the stripped version
            subprocess.run(
                ['strip-hints', str(file_path)],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"✓ {file_path}")
            return True
        else:
            print(f"⚠️  {file_path}: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ {file_path}: {e}")
        return False


def main():
    """Main function."""
    base_dir = Path(__file__).parent.parent
    
    services = [
        'backend-service/src',
        'sync-service/src',
        'nilm-service/src'
    ]
    
    total_files = 0
    modified_files = 0
    
    # Install strip-hints in all venvs first
    print("📦 Installing strip-hints in all environments...")
    for venv in ['backend-service', 'sync-service', 'nilm-service']:
        venv_pip = base_dir / venv / '.venv' / 'bin' / 'pip'
        if venv_pip.exists():
            subprocess.run([str(venv_pip), 'install', '-q', 'strip-hints'], check=True)
    
    for service in services:
        service_path = base_dir / service
        if not service_path.exists():
            print(f"⚠️  {service} not found")
            continue
        
        print(f"\n🔍 Processing {service}...")
        py_files = list(service_path.rglob('*.py'))
        
        # Use the appropriate venv's strip-hints
        service_name = service.split('/')[0]
        strip_hints_bin = base_dir / service_name / '.venv' / 'bin' / 'strip-hints'
        
        for py_file in py_files:
            if '__pycache__' in str(py_file):
                continue
            
            total_files += 1
            
            # Read original content
            original = py_file.read_text()
            
            # Use strip-hints
            result = subprocess.run(
                [str(strip_hints_bin), str(py_file), '--to-empty'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0 and result.stdout != original:
                # Write stripped version
                py_file.write_text(result.stdout)
                print(f"✓ {py_file}")
                modified_files += 1
            else:
                print(f"  {py_file} (no changes)")
    
    print(f"\n📊 Summary:")
    print(f"   Total files: {total_files}")
    print(f"   Modified: {modified_files}")
    print(f"   Unchanged: {total_files - modified_files}")


if __name__ == '__main__':
    main()
