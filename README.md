# PicoCalc SD Flasher

A simple Linux GUI tool to prepare SD cards for Clockwork PicoCalc devices.

## Features

- Detects removable storage devices (SD cards)
- Partitions the SD card (FAT32 + Linux ext4)
- Formats the partitions correctly
- Flashes firmware to the Linux partition

## Requirements

- Linux system
- Python 3.6+
- PyQt6
- sudo privileges (for disk operations)
- Required tools: `parted`, `mkfs.fat`, `mkfs.ext4`, `dd`

## Installation

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Make the script executable:

```bash
chmod +x flash_tool.py
```

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