#!/usr/bin/env python3

import sys
import os
import subprocess
import plistlib  # Import plistlib for parsing diskutil output
import logging  # Import the logging module
from PyQt6 import QtWidgets, QtCore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s',
    filename='flash_tool.log',
    filemode='w'  # Overwrite log file each time
)
logger = logging.getLogger(__name__)


class FlashTool(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("Initializing FlashTool application.")
        self.firmware_path = "fuzix.img"  # Default hardcoded path
        self.setWindowTitle("PicoCalc SD Flasher")
        self.setMinimumSize(500, 400)
        logger.info("Setting up UI.")
        self.setup_ui()
        logger.info("Refreshing device list on startup.")
        self.refresh_devices()
        logger.info("Initialization complete.")

    def setup_ui(self):
        logger.debug("Setting up UI elements.")
        central_widget = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout()

        # Device selection
        device_layout = QtWidgets.QHBoxLayout()
        self.device_combo = QtWidgets.QComboBox()
        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_devices)
        device_layout.addWidget(QtWidgets.QLabel("Select SD Card:"))
        device_layout.addWidget(self.device_combo)
        device_layout.addWidget(refresh_btn)

        # Firmware selection
        firmware_layout = QtWidgets.QHBoxLayout()
        self.firmware_label = QtWidgets.QLabel(self.firmware_path)
        select_firmware_btn = QtWidgets.QPushButton("Select Image")
        select_firmware_btn.clicked.connect(self.select_firmware)
        firmware_layout.addWidget(QtWidgets.QLabel("Firmware:"))
        firmware_layout.addWidget(self.firmware_label)
        firmware_layout.addWidget(select_firmware_btn)

        # Log output
        self.log_output = QtWidgets.QTextEdit()
        self.log_output.setReadOnly(True)

        # Control buttons
        button_layout = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton("Flash SD Card")
        self.start_btn.clicked.connect(self.flash_card)
        self.abort_btn = QtWidgets.QPushButton("Abort")
        self.abort_btn.clicked.connect(self.abort_process)
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.abort_btn)

        # Add all layouts to main layout
        main_layout.addLayout(device_layout)
        main_layout.addLayout(firmware_layout)
        main_layout.addWidget(self.log_output)
        main_layout.addLayout(button_layout)

        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        logger.debug("UI setup complete.")

    def log(self, message):
        """Append message to log output widget and log to file."""
        logger.info(message) # Log to file using standard logging
        self.log_output.append(message) # Append to GUI
        # Force UI update
        QtWidgets.QApplication.processEvents()

    def refresh_devices(self):
        """Get list of block devices that might be SD cards"""
        logger.info("Starting device refresh.")
        self.device_combo.clear()
        self.log("Searching for removable devices...")
        
        try:
            if sys.platform == 'darwin':  # macOS
                # Use diskutil to get external disks
                output = subprocess.check_output(
                    ['diskutil', 'list', '-plist', 'external'], 
                    universal_newlines=True)
                
                disk_list = plistlib.loads(output.encode('utf-8'))
                all_disks = disk_list.get('AllDisks', [])
                
                for disk_identifier in all_disks:
                    try:
                        # Get detailed info for each disk
                        info_output = subprocess.check_output(
                            ['diskutil', 'info', '-plist', disk_identifier],
                            universal_newlines=True)
                        disk_info = plistlib.loads(info_output.encode('utf-8'))
                        
                        if disk_info.get('RemovableMedia') or disk_info.get('Internal') == False:
                            device_path = f"/dev/{disk_identifier}"
                            size_bytes = disk_info.get('TotalSize', 0)
                            size_gb = size_bytes / (1024**3) # Convert to GB
                            label = disk_info.get('VolumeName', disk_identifier)
                            
                            display_text = f"{label} ({size_gb:.2f} GB) - {device_path}"
                            logger.debug(f"Found potential device: {display_text}")
                            self.device_combo.addItem(display_text, device_path)
                    except Exception as detail_error:
                        logger.error(f"Could not get detailed info for {disk_identifier}: {detail_error}", exc_info=True)
                        self.log(f"Could not get info for {disk_identifier}: {detail_error}")
            
            elif sys.platform.startswith('linux'): # Linux
                # Use lsblk to get removable devices
                output = subprocess.check_output(
                    ['lsblk', '-o', 'NAME,SIZE,RM,TYPE', '-n', '-p'], 
                    universal_newlines=True)
                
                for line in output.strip().split('\n'):
                    parts = line.split()
                    if len(parts) >= 4 and parts[2] == '1' and parts[3] == 'disk':
                        # This is a removable disk
                        device_path = parts[0]
                        size = parts[1]
                        logger.debug(f"Found potential device: {device_path} ({size})")
                        self.device_combo.addItem(f"{device_path} ({size})", device_path)
            
            else:
                logger.warning(f"Unsupported platform detected: {sys.platform}")
                self.log(f"Unsupported platform: {sys.platform}")
                    
            if self.device_combo.count() == 0:
                logger.info("No removable devices found after search.")
                self.log("No removable devices found.")
            else:
                logger.info(f"Found {self.device_combo.count()} potential device(s).")
                
        except FileNotFoundError as fnf_error:
            if 'diskutil' in str(fnf_error) or 'lsblk' in str(fnf_error):
                 logger.error(f"Required command not found: {fnf_error.filename}. Please ensure it's installed.", exc_info=True)
                 self.log(f"Error: Required command not found ({fnf_error.filename}). Please install it.")
            else:
                 logger.error(f"Error detecting devices (FileNotFoundError): {fnf_error}", exc_info=True)
                 self.log(f"Error detecting devices: {str(fnf_error)}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during device detection: {e}", exc_info=True)
            self.log(f"Error detecting devices: {str(e)}")
        logger.info("Device refresh finished.")

    def select_firmware(self):
        """Open file dialog to select firmware image"""
        logger.info("Opening firmware selection dialog.")
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Firmware Image",
            "",
            "Image Files (*.img *.bin);;All Files (*)",
        )

        if file_path:
            self.firmware_path = file_path
            self.firmware_label.setText(os.path.basename(file_path))
            logger.info(f"User selected firmware: {file_path}")
            self.log(f"Selected firmware: {file_path}")
        else:
            logger.info("Firmware selection cancelled by user.")

    def flash_card(self):
        """Start the flashing process"""
        logger.info("Flash process initiated by user.")
        if self.device_combo.count() == 0:
            logger.warning("Flash attempt failed: No device selected.")
            self.log("Error: No device selected.")
            return

        device = self.device_combo.currentData()
        logger.info(f"Target device selected: {device}")
        logger.warning(f"Data on {device} will be erased.")
        self.log(f"WARNING: This will ERASE ALL DATA on {device}!")
        self.log("Starting flash process...")

        # Disable UI during flashing
        self.start_btn.setEnabled(False)
        logger.debug("UI disabled during flash process.")

        try:
            # Step 1: Partitioning
            logger.info(f"Step 1: Partitioning {device}")
            self.log(f"Unmounting {device} if mounted...")
            # Use run_command for consistency and logging
            logger.debug(f"Attempting to unmount {device}")
            self.run_command(f"sudo umount {device}?* || true", check_return_code=False) # Allow failure if not mounted
            logger.debug(f"Unmount command finished for {device}")

            self.log(f"Creating partition table on {device}...")
            logger.debug(f"Running parted mklabel msdos on {device}")
            self.run_command(f"sudo parted -s {device} mklabel msdos")
            logger.debug(f"Partition table created on {device}")

            self.log("Creating partitions...")
            # Creating FAT32 partition
            logger.info(f"Creating FAT32 partition on {device} (1MiB to -33MiB).")
            self.run_command(
                f"sudo parted -s {device} mkpart primary fat32 1MiB -33MiB"
            )
            logger.debug(f"FAT32 partition created on {device}")
             # Creating ext4 partition
            logger.info(f"Creating ext4 partition on {device} (-33MiB to 100%).")
            self.run_command(f"sudo parted -s {device} mkpart primary ext4 -33MiB 100%")
            logger.debug(f"Ext4 partition created on {device}")
            logger.info("Partitioning complete.")

            # Step 2: Formatting
            logger.info(f"Step 2: Formatting partitions on {device}")
            self.log("Formatting FAT32 partition...")
            fat_partition = f"{device}p1" if sys.platform.startswith('linux') else f"{device}s1" # Adjust partition naming
            logger.info(f"Formatting {fat_partition} as FAT32.")
            self.run_command(f"sudo mkfs.fat -F32 {fat_partition}")
            logger.debug(f"FAT32 partition formatted ({fat_partition})")

            self.log("Formatting ext4 partition...")
            ext4_partition = f"{device}p2" if sys.platform.startswith('linux') else f"{device}s2" # Adjust partition naming
            logger.info(f"Formatting {ext4_partition} as ext4.")
            self.run_command(f"sudo mkfs.ext4 -F {ext4_partition}")
            logger.debug(f"Ext4 partition formatted ({ext4_partition})")
            logger.info("Formatting complete.")

            # Step 3: Flashing firmware
            logger.info(f"Step 3: Flashing firmware to {ext4_partition}")
            self.log(f"Flashing firmware '{os.path.basename(self.firmware_path)}' to {ext4_partition}...")
            logger.debug(f"Running dd command: sudo dd if='{self.firmware_path}' of='{ext4_partition}' bs=4M status=progress")
            self.run_command(
                f"sudo dd if='{self.firmware_path}' of='{ext4_partition}' bs=4M status=progress"
            )
            logger.info("Firmware flashing complete.")

            self.log("Flash completed successfully!")
            logger.info("Flash process completed successfully.")
        except Exception as e:
            logger.error(f"Error during flashing process: {e}", exc_info=True)
            self.log(f"Error during flashing: {str(e)}")
        finally:
            # Re-enable UI
            self.start_btn.setEnabled(True)
            logger.debug("UI re-enabled after flash process.")

    def run_command(self, cmd, check_return_code=True):
        """Run a shell command and log output"""
        logger.info(f"Executing command: {cmd}")
        self.log(f"Running: {cmd}")
        try:
            # Use Popen to potentially stream output later if needed, but capture for now
            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate() # Wait for completion

            if stdout:
                # Log stdout as debug, keep showing in GUI via self.log
                logger.debug(f"Command stdout:\n{stdout.strip()}")
                self.log(stdout.strip()) # Show command output in GUI too

            if stderr:
                 # dd writes status to stderr, treat as info unless return code is non-zero
                if "status=progress" in cmd and process.returncode == 0:
                    # Log progress as info, don't clutter GUI unless needed
                    logger.info(f"Command stderr (progress):\n{stderr.strip()}")
                    # self.log(f"Progress: {stderr.strip()}") # Optionally show progress in GUI
                else:
                    # Log actual errors as warning, show in GUI
                    logger.warning(f"Command stderr:\n{stderr.strip()}")
                    self.log(f"Error output: {stderr.strip()}") # Show errors in GUI

            if check_return_code and process.returncode != 0:
                logger.error(f"Command failed with return code {process.returncode}: {cmd}")
                self.log(f"Command failed with return code: {process.returncode}")
                raise Exception(f"Command failed: {cmd}")
            else:
                 logger.info(f"Command finished successfully (return code {process.returncode}): {cmd}")

        except Exception as e:
            logger.error(f"Failed to run command '{cmd}': {e}", exc_info=True)
            self.log(f"Failed to execute command: {cmd}")
            raise # Re-raise the exception to be caught by flash_card

    def abort_process(self):
        """Try to abort the current process"""
        logger.warning("Abort requested by user (not fully implemented).")
        self.log("Abort requested, but not implemented in this simple version.")
        self.log("Please wait for current operation to complete.")


if __name__ == "__main__":
    logger.info("Application starting.")
    app = QtWidgets.QApplication(sys.argv)
    window = FlashTool()
    window.show()
    logger.info("Entering main application event loop.")
    exit_code = app.exec()
    logger.info(f"Application exiting with code {exit_code}.")
    sys.exit(exit_code)
