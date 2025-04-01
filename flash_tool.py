#!/usr/bin/env python3

import sys
import os
import subprocess
import plistlib  # Import plistlib for parsing diskutil output
import logging  # Import the logging module
from PyQt6 import QtWidgets, QtCore
from validation import SDCardValidator, format_validation_results

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s',
    filename='logs/flash_tool.log',
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
                            logger.debug("Found potential device: %s", display_text)
                            self.device_combo.addItem(display_text, device_path)
                    except Exception as detail_error:
                        logger.error("Failed to get details for %s: %s", disk_identifier, detail_error, exc_info=True)
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
                        logger.debug("Found potential device: %s (%s)", device_path, size)
                        self.device_combo.addItem(f"{device_path} ({size})", device_path)
            
            else:
                logger.warning("Unsupported platform detected: %s", sys.platform)
                self.log("No removable devices found.")
                    
            if self.device_combo.count() == 0:
                logger.info("No removable devices found after search.")
                self.log("No removable devices found.")
            else:
                logger.info("Found %d potential devices.", self.device_combo.count())
                
        except FileNotFoundError as fnf_error:
            if 'diskutil' in str(fnf_error) or 'lsblk' in str(fnf_error):
                 logger.error("Command %s not found. Please install.", fnf_error.filename, exc_info=True)
                 self.log(f"Error: Required command not found ({fnf_error.filename}). Please install it.")
            else:
                 logger.error("Error detecting devices: %s", fnf_error, exc_info=True)
                 self.log(f"Error detecting devices: {str(fnf_error)}")
        except Exception as e:
            logger.error("Device detection error: %s", e, exc_info=True)
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
            logger.info("User selected firmware: %s", file_path)
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
        logger.info("Target device selected: %s", device)
        
        # Run validation checks
        validator = SDCardValidator()
        self.log("Running validation checks...")
        
        # Get device size in MB
        try:
            total_size_mb = self.get_device_size_mb(device)
            if total_size_mb <= 0:
                self.log(f"Error: Invalid device size detected")
                return
        except Exception as e:
            self.log(f"Error getting device size: {str(e)}")
            return
            
        validation_results = validator.validate_all(device, total_size_mb, self.firmware_path)
        self.log(format_validation_results(validation_results))
        
        # Check if any validation failed
        if not all(success for success, _ in validation_results.values()):
            self.log("Validation failed. Please fix the issues before proceeding.")
            return
            
        # Check for write protection
        if not self.check_write_protection(device):
            self.log("Error: Device appears to be write-protected. Cannot proceed.")
            return
            
        # Show destructive operation warning
        reply = QtWidgets.QMessageBox.warning(
            self,
            "Warning",
            f"WARNING: This will ERASE ALL DATA on {device}!\n\n"
            "Are you sure you want to continue?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.No:
            self.log("Operation cancelled by user.")
            return
            
        self.log("Starting flash process...")
        self.start_btn.setEnabled(False)
        logger.debug("UI disabled during flash process.")

        try:
            # Step 1: Partitioning
            logger.info("Step 1: Partitioning %s", device)
            self.log(f"Unmounting {device} if mounted...")
            if sys.platform == 'darwin':
                self.run_command(f"diskutil unmountDisk {device}", check_return_code=False)
            else:
                self.run_command(f"sudo umount {device}?* || true", check_return_code=False)

            # Get partition sequence from validator
            partition_commands = validator.validate_partition_sequence(device, total_size_mb)
            
            for cmd in partition_commands:
                self.log(f"Running: {cmd}")
                self.run_command(cmd)

            # Step 2: Formatting
            logger.info("Step 2: Formatting partitions on %s", device)
            self.log("Formatting FAT32 partition...")
            fat_partition = validator.get_partition_device(device, 1)
            
            if sys.platform == 'darwin':
                self.run_command(f"newfs_msdos -F 32 -v PicoCalc {fat_partition}")
            else:
                self.run_command(f"sudo mkfs.fat -F32 -v -I {fat_partition}")

            # Step 3: Flashing firmware
            linux_partition = validator.get_partition_device(device, 2)
            logger.info("Step 3: Flashing firmware to %s", linux_partition)
            self.log(f"Flashing firmware '{os.path.basename(self.firmware_path)}' to {linux_partition}...")
            self.run_command(
                f"sudo dd if='{self.firmware_path}' of='{linux_partition}' bs=4M status=progress"
            )
            
            # Step 4: Verify checksum (new)
            self.log("Verifying flashed image with checksum validation...")
            checksum_success, checksum_message = validator.verify_image_checksum(
                self.firmware_path, device, 2
            )
            
            if checksum_success:
                self.log("Checksum verification successful! Image flashed correctly.")
            else:
                self.log(f"Warning: {checksum_message}")
                self.log("The SD card may not have been flashed correctly.")
                # Don't return, continue with final steps

            self.log("Flash completed successfully!")
            logger.info("Flash process completed successfully.")
        except Exception as e:
            logger.error("Flashing error: %s", e, exc_info=True)
            self.log(f"Error during flash process: {str(e)}")
        finally:
            self.start_btn.setEnabled(True)
    
    def get_device_size_mb(self, device):
        """Get device size in MB using platform-specific methods"""
        if sys.platform == 'darwin':
            # Use diskutil info with plist format for reliable parsing
            disk_id = os.path.basename(device)
            result = subprocess.run(
                ['diskutil', 'info', '-plist', disk_id], 
                capture_output=True, text=True, check=True
            )
            
            # Parse plist output
            disk_info = plistlib.loads(result.stdout.encode('utf-8'))
            size_bytes = disk_info.get('TotalSize', 0)
        else:
            # Use lsblk with machine-readable output
            result = subprocess.run(
                ['lsblk', '--bytes', '--output', 'SIZE', '--nodeps', '--noheadings', device], 
                capture_output=True, text=True, check=True
            )
            size_bytes = int(result.stdout.strip())
            
        # Convert to MB
        total_size_mb = size_bytes // (1024 * 1024)
        return total_size_mb

    def run_command(self, cmd, check_return_code=True):
        """Run a shell command and log output with improved security"""
        logger.info("Executing command: %s", cmd)
        self.log(f"Running: {cmd}")
        
        # Handle privileged commands more securely
        if cmd.startswith("sudo ") and sys.platform.startswith('linux'):
            # Use pkexec if available which provides a GUI auth dialog on Linux
            try:
                # Check if pkexec is available
                subprocess.run(["which", "pkexec"], check=True, capture_output=True)
                # Replace sudo with pkexec
                cmd = "pkexec " + cmd[5:]
                logger.info("Using pkexec instead of sudo for: %s", cmd)
            except subprocess.CalledProcessError:
                # pkexec not available, warn user
                logger.warning("pkexec not available, using sudo which may require terminal access")
                # Continue with sudo
        
        try:
            # Avoid shell=True when not needed by splitting commands
            # But some commands (like those with pipes or redirects) still need shell
            needs_shell = any(c in cmd for c in '|>&;$')
            
            if needs_shell:
                process = subprocess.Popen(
                    cmd, 
                    shell=True, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    text=True
                )
            else:
                # Split command into args for more secure execution
                cmd_args = cmd.split()
                process = subprocess.Popen(
                    cmd_args,
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    text=True
                )
                
            stdout, stderr = process.communicate() # Wait for completion

            if stdout:
                logger.debug("Command stdout: %s", stdout.strip())
                self.log(stdout.strip())

            if stderr:
                 # dd writes status to stderr, treat as info unless return code is non-zero
                if "status=progress" in cmd and process.returncode == 0:
                    logger.info("Command progress: %s", stderr.strip())
                else:
                    logger.warning("Command stderr: %s", stderr.strip())
                    self.log(f"Error output: {stderr.strip()}")

            if check_return_code and process.returncode != 0:
                logger.error("Command failed with return code %d: %s", process.returncode, cmd)
                self.log(f"Command failed with return code: {process.returncode}")
                raise Exception(f"Command failed: {cmd}")
            else:
                 logger.info("Command finished (code %d): %s", process.returncode, cmd)

        except Exception as e:
            logger.error("Command execution failed '%s': %s", cmd, e, exc_info=True)
            self.log(f"Failed to execute command: {cmd}")
            raise # Re-raise the exception to be caught by flash_card

    def abort_process(self):
        """Try to abort the current process"""
        logger.warning("Abort requested by user (not fully implemented).")
        self.log("Abort requested, but not implemented in this simple version.")
        self.log("Please wait for current operation to complete.")

    def check_write_protection(self, device):
        """Check if the device is write-protected"""
        logger.info("Checking write protection for %s", device)
        self.log(f"Checking write protection status for {device}...")
        
        try:
            if sys.platform == 'darwin':  # macOS
                # Get diskutil info for write protection status
                result = subprocess.run(
                    ['diskutil', 'info', '-plist', os.path.basename(device)],
                    capture_output=True, text=True, check=True
                )
                
                disk_info = plistlib.loads(result.stdout.encode('utf-8'))
                
                # Check read-only status
                if disk_info.get('WritableMedia') == False:
                    logger.warning("Device %s is write-protected", device)
                    return False
                    
            elif sys.platform.startswith('linux'):  # Linux
                # Check write protection using blockdev command
                result = subprocess.run(
                    ['sudo', 'blockdev', '--getro', device],
                    capture_output=True, text=True, check=True
                )
                
                # If result is "1", the device is read-only
                if result.stdout.strip() == "1":
                    logger.warning("Device %s is write-protected", device)
                    return False
                    
                # Try to open the device for writing to test access
                try:
                    # Open file for writing (won't actually write anything)
                    fd = os.open(device, os.O_WRONLY)
                    os.close(fd)
                except PermissionError:
                    logger.warning("Permission denied to write to %s", device)
                    self.log("Permission denied to write to device. Try running as root or with sudo.")
                    return False
                except OSError as e:
                    logger.warning("Could not open %s for writing: %s", device, e)
                    return False
                    
            return True
        except subprocess.CalledProcessError as e:
            logger.error("Failed to check write protection: %s", e, exc_info=True)
            self.log(f"Warning: Could not check write protection status. Proceeding anyway.")
            # Return True to allow operation to continue
            return True
        except Exception as e:
            logger.error("Error checking write protection: %s", e, exc_info=True)
            self.log(f"Warning: Could not determine write protection status: {str(e)}")
            # Return True to allow operation to continue
            return True


if __name__ == "__main__":
    logger.info("Application starting.")
    app = QtWidgets.QApplication(sys.argv)
    window = FlashTool()
    window.show()
    logger.info("Entering main application event loop.")
    exit_code = app.exec()
    logger.info("Application exiting with code %d.", exit_code)
    sys.exit(exit_code)
