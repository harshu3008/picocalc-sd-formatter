# PicoCalc SD Card Formatter

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](https://github.com/yourusername/picocalc-sd-flasher/releases)
[![Powered by Cursor](https://img.shields.io/badge/Powered%20by-Cursor-blue?style=flat&logo=cursor&logoColor=white)](https://cursor.sh)

A GUI tool for formatting SD cards for use with the PicoCalc device. This tool creates the correct partition layout required by the PicoCalc operating system.

## AI Assistance Notice

This project was developed with the assistance of Cursor IDE's AI capabilities. The code has been:
- Generated and refined using AI pair programming
- Validated for functionality and security
- Reviewed and tested by human developers

## Features

- User-friendly GUI interface
- Automatic device detection
- Safe device validation
- Progress tracking
- Cross-platform support (Windows, macOS, Linux)
- Safety checks to prevent accidental system drive formatting

## Partition Layout

The tool creates two partitions on your SD card:
1. Main FAT32 partition for user data
2. 32MB system partition for firmware storage

## Prerequisites

### For Users
- Windows 10/11, macOS 10.15+, or Linux with Python 3.8+
- SD card reader
- Administrator/sudo privileges for device access

### For Developers
- Python 3.8 or higher
- pip (Python package installer)
- Git (for version control)

## Installation

### For Users
1. Download the latest release for your platform from the [GitHub Releases](https://github.com/yourusername/picocalc-sd-flasher/releases) page
2. Extract the zip file
3. Run the executable:
   - Windows: Double-click `PicoCalc-SD-Formatter.exe`
   - macOS: Double-click `PicoCalc-SD-Formatter.app`
   - Linux: Run `./PicoCalc-SD-Formatter` from terminal

### For Developers
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/picocalc-sd-flasher.git
   cd picocalc-sd-flasher
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the tool:
   ```bash
   python flash_tool.py
   ```

4. Build the executable (optional):
   ```bash
   python build.py
   ```

## Usage

1. Insert your SD card into your computer's card reader
2. Launch the application
3. Select your SD card from the dropdown menu
   - Use the "Show All Disks" button if your card isn't automatically detected
   - Use the "?" button for help with device selection
4. Click "Format SD Card" to begin the process
5. Follow the on-screen instructions and warnings

## Safety Features

- System drive detection and protection
- Removable media validation
- Write-protection checks
- Clear warning messages before destructive operations
- Partition alignment validation for optimal performance

## Building for Different Platforms

### Windows
```bash
python build.py
```

### macOS
```bash
python build.py
```

### Linux
```bash
python build.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Disclaimer

This software:
- May contain code snippets or patterns that were AI-generated
- Could include uncredited code from public sources
- Is provided "as is" without warranty of any kind
- Should be reviewed for security and functionality before use in production environments

Please review the code thoroughly and use at your own discretion. While efforts have been made to ensure quality and security, AI-generated code should always be validated for your specific use case.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- PyQt6 for the GUI framework
- PyInstaller for creating standalone executables
- The PicoCalc community for feedback and support
- [Cursor](https://cursor.sh) for AI-assisted development
- All unidentified code sources that may have contributed to this project 