# PicoCalc SD Card Preparation Tool

A Qt-based graphical tool for preparing SD cards for the PicoCalc device.

## Features

- Cross-platform support (Linux and macOS)
- Automatic device detection
- Partition creation and formatting
- Firmware flashing
- Validation and verification
- Progress reporting and real-time status updates
- Safe abort functionality

## Enhanced Safety Features

- System disk protection to prevent accidental data loss
- Comprehensive validation of target devices
- Secure privilege elevation
- Write protection detection
- Multiple confirmation steps for destructive operations

## Flash Memory Optimizations

- Proper partition alignment for optimal performance
- Flash parameter validation
- Optimal I/O size detection
- Safe block sizes for minimizing flash wear

## Prerequisites

- Linux or macOS
- Python 3.6+
- Qt6 (PyQt6)
- Required system tools:
  - Linux: `parted`, `mkfs.fat`, `dd`, `lsblk`, `blockdev`
  - macOS: `diskutil`, `newfs_msdos`, `dd`

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/username/picocalc-sd-flasher.git
   cd picocalc-sd-flasher
   ```

2. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Run the application:
   ```
   python flash_tool.py
   ```

2. Select your target SD card device
3. Select or use the default firmware image
4. Click "Flash SD Card"
5. Follow the on-screen instructions

## Error Recovery

If you encounter any issues during the flashing process:

1. Check the log output for specific error messages
2. Ensure your SD card is not write-protected
3. Verify you have appropriate permissions
4. Try a different SD card if problems persist

## Development

### Running Tests

```
python -m unittest test_validation.py
```

### Code Structure

- `flash_tool.py` - Main application and UI
- `validation.py` - SD card validation routines
- `test_validation.py` - Unit tests

## License

[Add your license information here] 