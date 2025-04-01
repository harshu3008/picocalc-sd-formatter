# PicoCalc SD Flasher

A GUI tool for flashing firmware to SD cards for the PicoCalc project.

## Features

- User-friendly GUI interface
- Support for multiple firmware images
- Automatic device detection
- Progress tracking
- Safety checks and validations
- Cross-platform support (Windows, macOS, Linux)

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
   - Windows: Double-click `PicoCalc-SD-Flasher.exe`
   - macOS: Double-click `PicoCalc-SD-Flasher.app`
   - Linux: Run `./PicoCalc-SD-Flasher` from terminal

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

3. Build the executable:
   ```bash
   python build.py
   ```

The executable will be created in the `dist` directory.

## Usage

1. Launch the application
2. Select your SD card device from the dropdown menu
3. Choose a firmware image to flash
4. Click "Flash SD Card" to begin the process
5. Follow the on-screen instructions

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

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- PyQt6 for the GUI framework
- PyInstaller for creating standalone executables
- The PicoCalc community for feedback and support 