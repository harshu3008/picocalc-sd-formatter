#!/usr/bin/env python3

import sys
import os
import subprocess
import plistlib  # Import plistlib for parsing diskutil output
import logging  # Import the logging module
from PyQt6 import QtWidgets, QtCore
from validation import SDCardValidator, format_validation_results
import threading
import time

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
        
        # Process tracking
        self.current_process = None
        self.process_running = False
        self.abort_requested = False
        
        logger.info("Setting up UI.")
        self.setup_ui()
        logger.info("Refreshing device list on startup.")
        self.refresh_devices()
        logger.info("Initialization complete.")

    def setup_ui(self):
        """Set up the application user interface"""
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        layout = QtWidgets.QVBoxLayout(central_widget)
        
        # Device selection group
        device_group = QtWidgets.QGroupBox("Select Target Device")
        device_layout = QtWidgets.QHBoxLayout(device_group)
        
        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.setMinimumWidth(250)
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_devices)
        
        device_layout.addWidget(self.device_combo)
        device_layout.addWidget(self.refresh_btn)
        layout.addWidget(device_group)
        
        # Firmware selection group
        firmware_group = QtWidgets.QGroupBox("Select Firmware")
        firmware_layout = QtWidgets.QHBoxLayout(firmware_group)
        
        self.firmware_label = QtWidgets.QLabel("fuzix.img")
        self.select_btn = QtWidgets.QPushButton("Select Firmware")
        self.select_btn.clicked.connect(self.select_firmware)
        
        firmware_layout.addWidget(self.firmware_label)
        firmware_layout.addWidget(self.select_btn)
        layout.addWidget(firmware_group)
        
        # Progress group
        progress_group = QtWidgets.QGroupBox("Operation Progress")
        progress_layout = QtWidgets.QVBoxLayout(progress_group)
        
        # Add progress bar
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_status = QtWidgets.QLabel("Ready")
        
        progress_layout.addWidget(self.progress_status)
        progress_layout.addWidget(self.progress_bar)
        layout.addWidget(progress_group)
        
        # Log output
        log_group = QtWidgets.QGroupBox("Output Log")
        log_layout = QtWidgets.QVBoxLayout(log_group)
        
        self.log_output = QtWidgets.QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setLineWrapMode(QtWidgets.QTextEdit.WidgetWidth)
        log_layout.addWidget(self.log_output)
        layout.addWidget(log_group)
        
        # Action buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        self.start_btn = QtWidgets.QPushButton("Flash SD Card")
        self.start_btn.clicked.connect(self.flash_card)
        
        self.abort_btn = QtWidgets.QPushButton("Abort")
        self.abort_btn.clicked.connect(self.abort_process)
        self.abort_btn.setEnabled(False)  # Disabled initially
        
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.abort_btn)
        layout.addLayout(button_layout)
        
        # Set stretch factors
        layout.setStretch(2, 1)  # Make log output take available space
        
        # Initial log
        self.log("Welcome to PicoCalc SD Flashing Tool")
        self.log("Please select a target device and firmware image")

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
        self.update_progress(5, "Validating device and firmware")
        
        # Get device size in MB
        try:
            total_size_mb = self.get_device_size_mb(device)
            if total_size_mb <= 0:
                self.log(f"Error: Invalid device size detected")
                self.update_progress(0, "Error: Invalid device size")
                return
        except Exception as e:
            self.log(f"Error getting device size: {str(e)}")
            self.update_progress(0, "Error: Failed to get device size")
            return
            
        validation_results = validator.validate_all(device, total_size_mb, self.firmware_path)
        self.log(format_validation_results(validation_results))
        
        # Check if any validation failed
        if not all(success for success, _ in validation_results.values()):
            self.log("Validation failed. Please fix the issues before proceeding.")
            self.update_progress(0, "Validation failed")
            return
            
        # Check for write protection
        self.update_progress(10, "Checking write protection")
        if not self.check_write_protection(device):
            self.log("Error: Device appears to be write-protected. Cannot proceed.")
            self.update_progress(0, "Error: Device is write-protected")
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
            self.update_progress(0, "Operation cancelled")
            return
            
        self.log("Starting flash process...")
        self.start_btn.setEnabled(False)
        self.abort_btn.setEnabled(True)  # Enable abort button during operation
        logger.debug("UI disabled during flash process.")

        try:
            # Step 1: Partitioning
            logger.info("Step 1: Partitioning %s", device)
            self.update_progress(15, "Unmounting device")
            self.log(f"Unmounting {device} if mounted...")
            if sys.platform == 'darwin':
                self.run_command(f"diskutil unmountDisk {device}", check_return_code=False)
            else:
                self.run_command(f"sudo umount {device}?* || true", check_return_code=False)

            # Get partition sequence from validator
            self.update_progress(20, "Creating partitions")
            partition_commands = validator.validate_partition_sequence(device, total_size_mb)
            
            # Run each partition command with progress updates
            for i, cmd in enumerate(partition_commands):
                progress = 20 + (i * 5)
                self.update_progress(progress, f"Partitioning: step {i+1}/3")
                self.log(f"Running: {cmd}")
                self.run_command(cmd)

            # Step 2: Formatting
            logger.info("Step 2: Formatting partitions on %s", device)
            self.update_progress(35, "Formatting FAT32 partition")
            self.log("Formatting FAT32 partition...")
            fat_partition = validator.get_partition_device(device, 1)
            
            if sys.platform == 'darwin':
                self.run_command(f"newfs_msdos -F 32 -v PicoCalc {fat_partition}")
            else:
                self.run_command(f"sudo mkfs.fat -F32 -v -I {fat_partition}")

            # Step 3: Flashing firmware
            linux_partition = validator.get_partition_device(device, 2)
            logger.info("Step 3: Flashing firmware to %s", linux_partition)
            self.update_progress(50, "Flashing firmware")
            self.log(f"Flashing firmware '{os.path.basename(self.firmware_path)}' to {linux_partition}...")
            
            # Run DD command with progress updates
            self.run_dd_with_progress(self.firmware_path, linux_partition)
            
            # Step 4: Verify checksum
            self.update_progress(90, "Verifying checksum")
            self.log("Verifying flashed image with checksum validation...")
            checksum_success, checksum_message = validator.verify_image_checksum(
                self.firmware_path, device, 2
            )
            
            if checksum_success:
                self.log("Checksum verification successful! Image flashed correctly.")
                self.update_progress(100, "Flash completed successfully")
            else:
                self.log(f"Warning: {checksum_message}")
                self.log("The SD card may not have been flashed correctly.")
                self.update_progress(100, "Completed with verification warnings")
                # Don't return, continue with final steps

            self.log("Flash completed successfully!")
            logger.info("Flash process completed successfully.")
        except Exception as e:
            logger.error("Flashing error: %s", e, exc_info=True)
            self.log(f"Error during flash process: {str(e)}")
            self.update_progress(0, "Error during flash process")
        finally:
            self.start_btn.setEnabled(True)
            self.abort_btn.setEnabled(False)  # Disable abort button when done

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
                
            # Store reference to currently running process
            self.current_process = process
            self.process_running = True
            
            stdout, stderr = process.communicate() # Wait for completion
            
            # Clear current process reference
            self.current_process = None
            self.process_running = False
            
            # Check if abort was requested and process completed anyway
            if self.abort_requested:
                self.abort_requested = False
                logger.warning("Process completed despite abort request")
                self.log("Process completed before abort could take effect.")

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
            # Clear process reference on exception
            self.current_process = None
            self.process_running = False
            
            logger.error("Command execution failed '%s': %s", cmd, e, exc_info=True)
            self.log(f"Failed to execute command: {cmd}")
            raise # Re-raise the exception to be caught by flash_card

    def abort_process(self):
        """Abort the current process"""
        logger.warning("Abort requested by user.")
        self.log("Attempting to abort the current operation...")
        
        if not self.process_running or self.current_process is None:
            self.log("No process is currently running to abort.")
            return
        
        self.abort_requested = True
        
        try:
            # First try gentle termination
            logger.info("Sending terminate signal to process.")
            self.current_process.terminate()
            
            # Give it a moment to terminate gracefully
            try:
                self.current_process.wait(timeout=2)
                self.log("Process terminated successfully.")
                logger.info("Process terminated successfully.")
            except subprocess.TimeoutExpired:
                # If it doesn't terminate in time, kill it forcefully
                logger.warning("Process did not terminate gracefully, forcing kill.")
                self.log("Process did not respond to termination, forcing kill...")
                self.current_process.kill()
                try:
                    self.current_process.wait(timeout=1)
                    self.log("Process killed.")
                    logger.info("Process killed.")
                except subprocess.TimeoutExpired:
                    self.log("Failed to kill process. It may still be running.")
                    logger.error("Failed to kill process. It may still be running.")
            
            # Reset process state
            self.current_process = None
            self.process_running = False
            
            # Re-enable the UI elements that might have been disabled
            self.start_btn.setEnabled(True)
            
            self.log("Operation aborted. Please check the device status before proceeding.")
            logger.info("Process abortion procedure completed.")
            
        except Exception as e:
            logger.error("Error aborting process: %s", e, exc_info=True)
            self.log(f"Error while trying to abort: {str(e)}")
            # Try to reset state anyway
            self.current_process = None
            self.process_running = False
            self.start_btn.setEnabled(True)

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

    def update_progress(self, value, status=None):
        """Update progress bar and status text"""
        self.progress_bar.setValue(value)
        if status:
            self.progress_status.setText(status)
        # Force UI update
        QtWidgets.QApplication.processEvents()
        
    def run_dd_with_progress(self, source, target):
        """Run dd command with progress monitoring"""
        # Get file size to calculate progress
        source_size = os.path.getsize(source)
        logger.info(f"Source file size: {source_size} bytes")
        
        # Create dd command with status reporting
        if sys.platform == 'darwin':
            # macOS version of dd doesn't have status=progress, use custom monitoring
            cmd = f"sudo dd if='{source}' of='{target}' bs=4M"
        else:
            # Linux dd with status=progress
            cmd = f"sudo dd if='{source}' of='{target}' bs=4M status=progress"
        
        # Set status
        self.update_progress(50, "Writing to device")
        
        # For macOS, we need to manually monitor the progress
        if sys.platform == 'darwin':
            process = subprocess.Popen(
                cmd, 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            
            # Store reference to current process
            self.current_process = process
            self.process_running = True
            
            # Start a separate thread to monitor dd progress on macOS
            monitor_thread = threading.Thread(
                target=self._monitor_dd_progress, 
                args=(process, source_size)
            )
            monitor_thread.daemon = True
            monitor_thread.start()
            
            # Wait for dd to complete
            stdout, stderr = process.communicate()
            
            # Clear process reference
            self.current_process = None
            self.process_running = False
            
            # Log output
            if stdout:
                self.log(stdout.strip())
            if stderr:
                self.log(stderr.strip())
            
            # Check return code
            if process.returncode != 0:
                logger.error("DD command failed with return code %d", process.returncode)
                self.log(f"DD command failed with return code: {process.returncode}")
                raise Exception("DD command failed")
        else:
            # For Linux, use the standard run_command with status=progress
            self.run_command(cmd)
        
        # Final progress update
        self.update_progress(85, "DD write completed")

    def _monitor_dd_progress(self, process, total_size):
        """Monitor dd progress on macOS using periodic status checks"""
        try:
            while process.poll() is None and self.process_running:
                if self.abort_requested:
                    # Stop monitoring if abort was requested
                    return
                    
                # Use pinfo to check how much has been written
                try:
                    # Get target device from process error output (hack)
                    target_info = subprocess.check_output(
                        f"ps -p {process.pid} -o command= | grep -o 'of=[^ ]*'",
                        shell=True, text=True
                    ).strip()
                    
                    if target_info:
                        target = target_info.split('=')[1].strip("'\"")
                        # Get current size of target
                        if os.path.exists(target):
                            current_size = os.path.getsize(target)
                            # Calculate progress percentage
                            progress = min(85, 50 + int((current_size / total_size) * 35))
                            self.update_progress(progress, f"Writing: {current_size/1024/1024:.1f}MB of {total_size/1024/1024:.1f}MB")
                except Exception as e:
                    logger.debug(f"Error monitoring dd progress: {str(e)}")
                    
                # Sleep briefly before checking again
                time.sleep(1)
        except Exception as e:
            logger.error(f"Error in dd monitor thread: {str(e)}")
            # Don't update UI directly from thread - could cause issues


if __name__ == "__main__":
    logger.info("Application starting.")
    app = QtWidgets.QApplication(sys.argv)
    window = FlashTool()
    window.show()
    logger.info("Entering main application event loop.")
    exit_code = app.exec()
    logger.info("Application exiting with code %d.", exit_code)
    sys.exit(exit_code)
