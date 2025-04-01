# PicoCalc SD Card Flasher

A GUI tool for flashing SD cards with PicoCalc firmware.

## Project Structure

```
.
├── flash_tool.py      # Main application
├── validation.py      # Validation logic
├── test_validation.py # Test suite
├── logs/             # Log files directory
│   └── .gitkeep      # Keeps logs directory in git
└── .gitignore        # Git ignore rules
```

## Logging

Logs are stored in the `logs/` directory. The main application log file is `logs/flash_tool.log`. Log files are not versioned in git but the `logs/` directory is maintained to ensure proper directory structure.

## Development

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Unix/macOS
   # or
   .\venv\Scripts\activate  # On Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python flash_tool.py
   ```

4. Run tests:
   ```bash
   python -m unittest test_validation.py
   ```

## Requirements

- Python 3.6+
- PyQt6
- Platform-specific tools:
  - Linux: `parted`, `mkfs.fat`, `lsblk`
  - macOS: `diskutil`, `newfs_msdos`

## Features

- Detects removable storage devices (SD cards)
- Partitions the SD card (FAT32 + Linux ext4)
- Formats the partitions correctly
- Flashes firmware to the Linux partition

## Usage

1. Insert your SD card
2. Launch the application:

```bash
./flash_tool.py
```

3. Select your SD card from the dropdown
4. (Optional) Select a custom firmware image file
5. Click "Flash SD Card"

## Warning

This application will erase ALL data on the selected SD card. Make sure to backup any important data before using this tool. 