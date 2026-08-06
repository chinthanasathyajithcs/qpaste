"""
PyInstaller Build Script for QPaste.
Compiles the application into a standalone Windows executable.
"""
import os
import subprocess
import sys

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scripts_dir = os.path.join(root_dir, "scripts")
    src_dir = os.path.join(root_dir, "src")
    main_script = os.path.join(src_dir, "main.py")
    icon_path = os.path.join(root_dir, "assets", "icon.ico")
    icon_script = os.path.join(scripts_dir, "generate_icons.py")
    
    # Change CWD to project root so dist and build folders are created there
    os.chdir(root_dir)

    print("Generating icon assets from SVG...")
    subprocess.check_call([sys.executable, icon_script])
    
    print("Building QPaste Executable...")
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "QPaste",
        "--windowed", # No console window
        "--onefile",  # Output a single .exe
        "--icon", icon_path,
        "--add-data", f"assets{os.pathsep}assets",
        "--add-data", f"src{os.pathsep}src",
        main_script
    ]
    
    subprocess.check_call(cmd)
    
    print("\nBuild successful! Executable is located in the 'dist' directory.")

if __name__ == "__main__":
    main()
