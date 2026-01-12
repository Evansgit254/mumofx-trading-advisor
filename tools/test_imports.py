import os
import importlib
import sys

def test_imports(start_dir):
    print(f"Testing imports in {start_dir}...")
    success = True
    for root, dirs, files in os.walk(start_dir):
        if ".venv" in root or "__pycache__" in root or ".git" in root:
            continue
            
        for file in files:
            if file.endswith(".py") and file != "main.py" and file != "test_imports.py":
                # Construct module path
                rel_path = os.path.relpath(os.path.join(root, file), start_dir)
                module_name = rel_path.replace(os.path.sep, ".")[:-3]
                
                try:
                    importlib.import_module(module_name)
                    print(f"✅ Imported {module_name}")
                except Exception as e:
                    print(f"❌ Failed to import {module_name}: {e}")
                    success = False
    
    if success:
        print("\nAll modules imported successfully.")
        sys.exit(0)
    else:
        print("\nSome imports failed.")
        sys.exit(1)

if __name__ == "__main__":
    # Add project root to sys.path
    project_root = os.getcwd()
    sys.path.append(project_root)
    test_imports(project_root)
