#!/usr/bin/env python3
"""Script to remove type hints from Python files."""

import re
import sys
from pathlib import Path


def remove_type_hints(content: str) -> str:
    """Remove type hints from Python code."""
    
    # Remove function return type hints: ) -> Type:
    content = re.sub(r'\)\s*->\s*[^:]+:', '):', content)
    
    # Remove parameter type hints: param: Type
    # This is tricky, need to handle default values
    content = re.sub(r'(\w+)\s*:\s*[^=,)]+(\s*[=,)])', r'\1\2', content)
    
    # Remove variable annotations: var: Type = value
    content = re.sub(r'^(\s*)(\w+)\s*:\s*[^=]+\s*=', r'\1\2 =', content, flags=re.MULTILINE)
    
    # Remove standalone type annotations: var: Type (without assignment)
    # Be careful not to remove dict keys
    lines = content.split('\n')
    new_lines = []
    for line in lines:
        # Skip if it's a dict/class definition or import
        if not any(x in line for x in ['class ', 'import ', 'from ', ':', '{', '}']):
            # Remove standalone annotations
            line = re.sub(r'^(\s*)(\w+)\s*:\s*[^\s]+\s*$', r'\1# \2 annotation removed', line)
        new_lines.append(line)
    
    return '\n'.join(new_lines)


def process_file(file_path: Path) -> bool:
    """Process a single Python file to remove type hints."""
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        
        # Remove type hints
        new_content = remove_type_hints(content)
        
        if new_content != original_content:
            file_path.write_text(new_content, encoding='utf-8')
            print(f"✓ {file_path}")
            return True
        else:
            print(f"  {file_path} (no changes)")
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
    
    for service in services:
        service_path = base_dir / service
        if not service_path.exists():
            print(f"⚠️  {service} not found")
            continue
        
        print(f"\n🔍 Processing {service}...")
        py_files = list(service_path.rglob('*.py'))
        
        for py_file in py_files:
            if '__pycache__' in str(py_file):
                continue
            
            total_files += 1
            if process_file(py_file):
                modified_files += 1
    
    print(f"\n📊 Summary:")
    print(f"   Total files: {total_files}")
    print(f"   Modified: {modified_files}")
    print(f"   Unchanged: {total_files - modified_files}")


if __name__ == '__main__':
    main()
