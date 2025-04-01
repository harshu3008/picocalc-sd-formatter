#!/usr/bin/env python3

import os
import sys
import shutil
import subprocess
from datetime import datetime

def clean_build():
    """Clean previous build artifacts"""
    print("Cleaning previous build artifacts...")
    dirs_to_clean = ['build', 'dist']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
    print("Clean complete.")

def build_executable():
    """Build the executable using PyInstaller"""
    print("Building executable...")
    
    # Base PyInstaller command
    cmd = [
        'pyinstaller',
        '--name=PicoCalc-SD-Formatter',  # Name of the executable
        '--windowed',  # Don't show console window
        '--onefile',  # Create a single executable file
        '--clean',  # Clean PyInstaller cache
        '--noconfirm',  # Replace existing build without asking
        '--hidden-import=PyQt6',
        '--hidden-import=PyQt6.QtCore',
        '--hidden-import=PyQt6.QtGui',
        '--hidden-import=PyQt6.QtWidgets',
        '--hidden-import=plistlib',
        '--hidden-import=logging',
        '--hidden-import=urllib.request',
        '--hidden-import=threading',
        '--hidden-import=validation',  # Include the validation module
        '--add-data=validation.py:validation.py',  # Include validation.py
        '--add-data=README.md:README.md',  # Include README
        '--add-data=LICENSE:LICENSE',  # Include LICENSE
        '--add-data=requirements.txt:requirements.txt',  # Include requirements
    ]
    
    # Add icon if it exists
    if sys.platform == 'darwin':  # macOS
        icon_path = 'assets/icon.icns'
    else:  # Windows/Linux
        icon_path = 'assets/icon.ico'
        
    if os.path.exists(icon_path):
        cmd.append(f'--icon={icon_path}')
        print(f"Using icon: {icon_path}")
    else:
        print("No icon found, building without icon")
    
    # Add assets directory if it exists
    if os.path.exists('assets'):
        cmd.append('--add-data=assets:assets')
        print("Including assets directory")
    
    # Add the main script
    cmd.append('sd_formatter.py')
    
    # Run PyInstaller
    subprocess.run(cmd, check=True)
    print("Build complete.")

def create_version_file():
    """Create a version file with build information"""
    version = "1.0.0"  # Update this for each release
    build_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    version_info = f"""Version: {version}
Build Date: {build_date}
Platform: {sys.platform}
Python Version: {sys.version}
"""
    
    with open('dist/VERSION.txt', 'w') as f:
        f.write(version_info)
    print("Version file created.")

def create_release_package():
    """Create a release package with necessary files"""
    print("Creating release package...")
    
    # Create release directory
    release_dir = 'release'
    if os.path.exists(release_dir):
        shutil.rmtree(release_dir)
    os.makedirs(release_dir)
    
    # Copy executable and necessary files
    if sys.platform == 'darwin':
        shutil.copytree('dist/PicoCalc-SD-Formatter.app', os.path.join(release_dir, 'PicoCalc-SD-Formatter.app'))
    else:
        shutil.copy('dist/PicoCalc-SD-Formatter', release_dir)
    
    shutil.copy('dist/VERSION.txt', release_dir)
    shutil.copy('README.md', release_dir)
    
    # Create a zip file of the release
    shutil.make_archive(
        f'PicoCalc-SD-Formatter-v1.0.0-{sys.platform}',
        'zip',
        release_dir
    )
    
    print("Release package created.")

def main():
    """Main build process"""
    try:
        clean_build()
        build_executable()
        create_version_file()
        create_release_package()
        print("\nBuild process completed successfully!")
        print("\nNext steps:")
        print("1. Test the executable in the 'dist' directory")
        print("2. Create a new release on GitHub")
        print("3. Upload the zip file from the current directory")
    except Exception as e:
        print(f"Error during build process: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 