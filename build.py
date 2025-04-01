#!/usr/bin/env python3

import os
import sys
import shutil
import subprocess
from datetime import datetime

class PyInstallerError(Exception):
    """Custom exception for PyInstaller build failures"""
    pass

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
    ]
    
    # Add data files
    data_files = [
        ('validation.py', 'validation.py'),
        ('README.md', 'README.md'),
        ('LICENSE', 'LICENSE'),
        ('requirements.txt', 'requirements.txt')
    ]
    
    for src, dest in data_files:
        if os.path.exists(src):
            cmd.append(f'--add-data={src}:{dest}')
            print(f"Including data file: {src}")
        else:
            print(f"Warning: Data file {src} not found, skipping")
    
    # Add icon if it exists
    if sys.platform == 'darwin':  # macOS
        icon_path = 'assets/icon.icns'
    elif sys.platform == 'win32':  # Windows
        icon_path = 'assets/icon.ico'
    else:  # Linux
        icon_path = 'assets/icon.ico'
        
    if os.path.exists(icon_path):
        cmd.append(f'--icon={icon_path}')
        print(f"Using icon: {icon_path}")
    else:
        print("No icon found, building without icon")
    
    # Add assets directory if it exists
    if os.path.exists('assets'):
        if sys.platform == 'win32':  # Windows
            cmd.append('--add-data=assets;assets')
        else:  # macOS and Linux
            cmd.append('--add-data=assets:assets')
        print("Including assets directory")
    
    # Add the main script
    cmd.append('sd_formatter.py')
    
    # Run PyInstaller
    print(f"Running PyInstaller with command: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"PyInstaller failed with return code {result.returncode}")
        print("STDOUT:")
        print(result.stdout)
        print("STDERR:")
        print(result.stderr)
        raise PyInstallerError(f"PyInstaller build failed with return code {result.returncode}")
    else:
        print("PyInstaller completed successfully")
    
    # Verify the executable was created
    if sys.platform == 'darwin':  # macOS
        expected_path = 'dist/PicoCalc-SD-Formatter.app'
        if os.path.isdir(expected_path):
            print(f"macOS app bundle created at: {expected_path}")
        else:
            print(f"Error: macOS app bundle not found at {expected_path}")
            print("Contents of dist directory:")
            print(os.listdir('dist'))
            raise FileNotFoundError(f"macOS app bundle not found at {expected_path}")
    elif sys.platform == 'win32':  # Windows
        expected_path = 'dist/PicoCalc-SD-Formatter.exe'
        if os.path.isfile(expected_path):
            print(f"Windows executable created at: {expected_path}")
        else:
            print(f"Error: Windows executable not found at {expected_path}")
            print("Contents of dist directory:")
            print(os.listdir('dist'))
            raise FileNotFoundError(f"Windows executable not found at {expected_path}")
    else:  # Linux
        expected_path = 'dist/PicoCalc-SD-Formatter'
        if os.path.isfile(expected_path):
            print(f"Linux executable created at: {expected_path}")
        else:
            print(f"Error: Linux executable not found at {expected_path}")
            print("Contents of dist directory:")
            print(os.listdir('dist'))
            raise FileNotFoundError(f"Linux executable not found at {expected_path}")
    
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
    if sys.platform == 'darwin':  # macOS
        if os.path.exists('dist/PicoCalc-SD-Formatter.app'):
            shutil.copytree('dist/PicoCalc-SD-Formatter.app', os.path.join(release_dir, 'PicoCalc-SD-Formatter.app'))
        else:
            print("Warning: macOS app bundle not found, skipping copy")
    elif sys.platform == 'win32':  # Windows
        if os.path.exists('dist/PicoCalc-SD-Formatter.exe'):
            shutil.copy('dist/PicoCalc-SD-Formatter.exe', release_dir)
        else:
            print("Warning: Windows executable not found, skipping copy")
    else:  # Linux
        if os.path.exists('dist/PicoCalc-SD-Formatter'):
            shutil.copy('dist/PicoCalc-SD-Formatter', release_dir)
        else:
            print("Warning: Linux executable not found, skipping copy")
    
    # Copy version file
    if os.path.exists('dist/VERSION.txt'):
        shutil.copy('dist/VERSION.txt', release_dir)
    else:
        print("Warning: VERSION.txt not found, skipping copy")
    
    # Copy README
    if os.path.exists('README.md'):
        shutil.copy('README.md', release_dir)
    else:
        print("Warning: README.md not found, skipping copy")
    
    # Create a zip file of the release
    platform_suffix = 'win' if sys.platform == 'win32' else ('mac' if sys.platform == 'darwin' else 'linux')
    zip_filename = f'PicoCalc-SD-Formatter-v1.0.0-{platform_suffix}'
    
    try:
        shutil.make_archive(
            zip_filename,
            'zip',
            release_dir
        )
        print(f"Release package created: {zip_filename}.zip")
    except Exception as e:
        print(f"Error creating zip archive: {e}")
    
    print("Release package creation complete.")

def ad_hoc_sign_macos_app(app_path):
    """Sign the macOS application with an ad hoc signature"""
    if sys.platform != 'darwin':
        return
        
    print("Starting ad hoc code signing process...")
    try:
        # Sign the application with ad hoc signature
        sign_cmd = [
            'codesign',
            '--sign', '-',  # Use '-' for ad hoc signing
            '--deep',
            '--force',
            app_path
        ]
        subprocess.run(sign_cmd, check=True)
        print("Application signed successfully with ad hoc signature")
        print("\nNOTE: Users will still see Gatekeeper warnings when running the app.")
        print("They can bypass this by:")
        print("1. Right-clicking the app and selecting 'Open'")
        print("2. Clicking 'Open' in the security dialog that appears")
    except subprocess.CalledProcessError as e:
        print(f"Error during signing process: {e}")
    except Exception as e:
        print(f"Unexpected error during signing: {e}")

def main():
    """Main build process"""
    try:
        print(f"Starting build process on platform: {sys.platform}")
        print(f"Python version: {sys.version}")
        print(f"Current directory: {os.getcwd()}")
        
        # Create dist directory if it doesn't exist
        os.makedirs('dist', exist_ok=True)
        
        clean_build()
        build_executable()
        create_version_file()
        
        # Sign with ad hoc signature if on macOS
        if sys.platform == 'darwin':
            app_path = 'dist/PicoCalc-SD-Formatter.app'
            if os.path.exists(app_path):
                ad_hoc_sign_macos_app(app_path)
        
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