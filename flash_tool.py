#!/usr/bin/env python3

import sys
import os
import subprocess
import plistlib  # Import plistlib for parsing diskutil output
import logging  # Import the logging module
from PyQt6 import QtWidgets, QtCore, QtGui
from validation import SDCardValidator, format_validation_results
import threading
import time
import stat  # Import for file permissions
import tempfile  # Import for temporary directory handling

def setup_logging():
    """Set up logging with proper directory handling"""
    try:
        # Use a temporary directory for logs if we can't write to the preferred location
        if sys.platform == 'darwin':
            # Try to use ~/Library/Logs first
            preferred_logs_dir = os.path.expanduser('~/Library/Logs/PicoCalc-SD-Formatter')
            try:
                os.makedirs(preferred_logs_dir, mode=0o700, exist_ok=True)
                logs_dir = preferred_logs_dir
            except (OSError, IOError):
                # Fall back to temporary directory
                logs_dir = os.path.join(tempfile.gettempdir(), 'PicoCalc-SD-Formatter-Logs')
                os.makedirs(logs_dir, mode=0o700, exist_ok=True)
        else:
            # On other platforms, use ~/.picocalc-sd-formatter/logs/
            logs_dir = os.path.expanduser('~/.picocalc-sd-formatter/logs')
            os.makedirs(logs_dir, mode=0o700, exist_ok=True)
        
        # Configure logging
        log_file = os.path.join(logs_dir, 'flash_tool.log')
        
        # Create or touch the log file to ensure proper permissions
        with open(log_file, 'a') as f:
            os.chmod(log_file, 0o600)  # rw for user only
            
        print(f"Log file path: {log_file}")  # Debug print
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s',
            filename=log_file,
            filemode='w'  # Overwrite log file each time
        )
        
        # Add a console handler to see logs in the terminal
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        formatter = logging.Formatter('%(levelname)s - %(message)s')
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)
        
        return logging.getLogger(__name__)
        
    except Exception as e:
        # If we can't set up file logging, fall back to console-only logging
        print(f"Warning: Could not set up file logging: {str(e)}")
        logging.basicConfig(
            level=logging.INFO,
            format='%(levelname)s - %(message)s',
            stream=sys.stdout
        )
        return logging.getLogger(__name__)

# Configure logging
logger = setup_logging()

class FlashTool(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("Initializing FlashTool application.")
        self.setWindowTitle("PicoCalc SD Card Formatter")
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
        self.device_combo.setToolTip("Select the main disk device (e.g., /dev/disk4 on macOS or /dev/sdb on Linux)\n"
                                   "not individual partitions. The tool will handle partitioning for you.")
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_devices)
        
        # Add help button for device selection
        self.device_help_btn = QtWidgets.QPushButton("?")
        self.device_help_btn.setMaximumWidth(30)
        self.device_help_btn.clicked.connect(self.show_device_help)
        self.device_help_btn.setToolTip("Get help with device selection")
        
        # Add debug button to show all disks
        self.show_all_disks_btn = QtWidgets.QPushButton("Show All Disks")
        self.show_all_disks_btn.clicked.connect(self.show_all_disks)
        self.show_all_disks_btn.setToolTip("Show all available disks for debugging")
        
        device_layout.addWidget(self.device_combo)
        device_layout.addWidget(self.refresh_btn)
        device_layout.addWidget(self.device_help_btn)
        device_layout.addWidget(self.show_all_disks_btn)
        layout.addWidget(device_group)

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
        self.log_output.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.WidgetWidth)
        log_layout.addWidget(self.log_output)
        layout.addWidget(log_group)
        
        # Action buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        self.start_btn = QtWidgets.QPushButton("Format SD Card")
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
        self.log("Welcome to PicoCalc SD Card Formatter")
        self.log("Please select a target device to format")

    def log(self, message):
        """Append message to log output widget and log to file."""
        logger.info(message) # Log to file using standard logging
        self.log_output.append(message) # Append to GUI
        # Force UI update
        QtWidgets.QApplication.processEvents()

    def refresh_devices(self):
        """Get list of block devices that might be SD cards"""
        logger.info("Starting device refresh.")
        
        # Temporarily disconnect the signal to prevent triggering the manual input
        self.device_combo.currentIndexChanged.disconnect() if self.device_combo.receivers(self.device_combo.currentIndexChanged) > 0 else None
        
        self.device_combo.clear()
        self.log("Searching for removable devices...")
        
        # Add a manual entry option at the top
        self.device_combo.addItem("-- Enter device path manually --", "manual")
        
        try:
            # DEBUGGING: Log platform information
            logger.info(f"Platform: {sys.platform}")
            self.log(f"Platform detected: {sys.platform}")
            
            if sys.platform == 'darwin':  # macOS
                # DEBUGGING: Log all diskutil commands and outputs
                self.log("======== DEBUGGING INFO START ========")
                
                # Get raw list output first (just for debugging)
                try:
                    raw_output = subprocess.check_output(
                        ['diskutil', 'list'], 
                        universal_newlines=True, stderr=subprocess.STDOUT)
                    logger.debug(f"Raw diskutil list output:\n{raw_output}")
                    self.log(f"Raw diskutil output:\n{raw_output}")
                except Exception as e:
                    logger.error(f"Failed to get raw diskutil output: {e}")
                    self.log(f"Failed to get raw diskutil output: {e}")
                
                # Get external disk list for actual processing
                try:
                    # Try to list external disks first
                    external_cmd = ['diskutil', 'list', 'external']
                    logger.debug(f"Running command: {' '.join(external_cmd)}")
                    external_output = subprocess.check_output(
                        external_cmd, 
                        universal_newlines=True, stderr=subprocess.STDOUT)
                    logger.debug(f"External diskutil output:\n{external_output}")
                    self.log(f"External disk output:\n{external_output}")
                    
                    # Parse the output for disk identifiers
                    detected_disks = []
                    for line in external_output.splitlines():
                        line = line.strip()
                        # Looking for lines like "/dev/disk4 (external, physical):"
                        if line.startswith("/dev/disk") and "external" in line:
                            disk_id = line.split()[0].replace("/dev/", "")
                            logger.debug(f"Found external disk: {disk_id}")
                            detected_disks.append(disk_id)
                            
                    self.log(f"Detected external disks: {detected_disks}")
                    
                    # Process each detected disk
                    for disk_id in detected_disks:
                        try:
                            # Get disk info
                            info_cmd = ['diskutil', 'info', '-plist', disk_id]  # Use plist format for reliable parsing
                            logger.debug(f"Running command: {' '.join(info_cmd)}")
                            info_output = subprocess.check_output(
                                info_cmd,
                                universal_newlines=True, stderr=subprocess.STDOUT)
                                
                            # Parse plist output
                            disk_info = plistlib.loads(info_output.encode('utf-8'))
                            
                            # Get disk information
                            device_path = f"/dev/{disk_id}"
                            size_gb = disk_info.get('TotalSize', 0) / (1024 * 1024 * 1024)  # Convert to GB
                            volume_name = disk_info.get('VolumeName', 'NO NAME')
                            
                            # Build display string and add to combo box
                            display_text = f"{volume_name} ({size_gb:.1f} GB) - {device_path}"
                            logger.debug(f"Adding device to combo box: {display_text}")
                            self.log(f"Adding device: {display_text}")
                            self.device_combo.addItem(display_text, device_path)
                            
                        except Exception as detail_error:
                            logger.error(f"Failed to process disk {disk_id}: {detail_error}", exc_info=True)
                            self.log(f"Error processing disk {disk_id}: {str(detail_error)}")
                            
                    # Check if we found any disks
                    if not detected_disks:
                        logger.warning("No external disks detected from diskutil output")
                        self.log("No external disks detected")
                        
                except Exception as e:
                    logger.error(f"Failed to get external disk list: {e}", exc_info=True)
                    self.log(f"Failed to get external disk list: {str(e)}")
                    
                self.log("======== DEBUGGING INFO END ========")
            
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
                    
            if self.device_combo.count() <= 1: # Only the manual option
                logger.info("No removable devices found after search.")
                self.log("No removable devices found. You can enter a device path manually or try 'Show All Disks'.")
            else:
                logger.info("Found %d potential devices.", self.device_combo.count() - 1) # Exclude manual option
                
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
        
        # Reconnect the signal after populating the combo box
        self.device_combo.currentIndexChanged.connect(self.on_device_selection_changed)

    def on_device_selection_changed(self, index):
        """Handle device selection changes"""
        if index >= 0:
            device = self.device_combo.currentData()
            if device == "manual":
                self.prompt_for_device_path()
                
    def prompt_for_device_path(self):
        """Prompt the user to enter a device path manually"""
        device_path, ok = QtWidgets.QInputDialog.getText(
            self,
            "Enter Device Path",
            "Enter the full path to your SD card device\n(e.g., /dev/disk4 on macOS or /dev/sdb on Linux):"
        )
        
        if ok and device_path:
            # Verify that the path looks reasonable
            if (sys.platform == 'darwin' and device_path.startswith('/dev/disk')) or \
               (sys.platform.startswith('linux') and device_path.startswith('/dev/')):
                # Add the manual device to the combo box
                self.device_combo.clear()  # Remove the "Enter manually" option
                display_text = f"MANUAL: {device_path}"
                self.device_combo.addItem(display_text, device_path)
                self.log(f"Manually selected device: {device_path}")
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Invalid Device Path",
                    f"The path '{device_path}' does not appear to be a valid device path."
                )
                # Reset to the manual option
                self.refresh_devices()

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
        self.update_progress(5, "Validating device")
        
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
            
        validation_results = validator.validate_all(device, total_size_mb)
        self.log(format_validation_results(validation_results))
        
        # Check if any REQUIRED validation failed
        required_failed = any(
            not success for check, (success, _) in validation_results.items() 
            if check in ["device", "partition_sequence", "formatting"]
        )
        
        if required_failed:
            self.log("Required validation checks failed. Please fix the issues before proceeding.")
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
            
        self.log("Starting format process...")
        self.start_btn.setEnabled(False)
        self.abort_btn.setEnabled(True)  # Enable abort button during operation
        logger.debug("UI disabled during format process.")

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
                progress = 20 + (i * 10)
                self.update_progress(progress, f"Partitioning: step {i+1}/{len(partition_commands)}")
                self.log(f"Running: {cmd}")
                self.run_command(cmd)

            # Step 2: Formatting - this is only needed on Linux since diskutil handles formatting on macOS
            if sys.platform != 'darwin':
                logger.info("Step 2: Formatting partitions on %s", device)
                self.update_progress(35, "Formatting FAT32 partition")
                self.log("Formatting FAT32 partition...")
                fat_partition = validator.get_partition_device(device, 1)
                self.run_command(f"sudo mkfs.fat -F32 -v -I {fat_partition}")
            else:
                # On macOS, diskutil already formatted the partitions
                logger.info("Step 2: Skipping explicit formatting as diskutil handled it")
                self.update_progress(35, "Partitions formatted by diskutil")
                self.log("Partitions already formatted by diskutil")

            self.log("Format completed successfully!")
            self.update_progress(100, "Format completed successfully")
            logger.info("Format process completed successfully.")
        except Exception as e:
            logger.error("Formatting error: %s", e, exc_info=True)
            self.log(f"Error during format process: {str(e)}")
            self.update_progress(0, "Error during format process")
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

    def show_device_help(self):
        """Show a help dialog with information about device selection"""
        help_text = """
<h3>How to Select the Correct Device</h3>
<p>When using an SD card, you may see multiple entries for the same physical device:</p>
<ul>
    <li>On macOS, you might see <b>/dev/disk4</b> and also <b>/dev/disk4s1</b> (a partition)</li>
    <li>On Linux, you might see <b>/dev/sdb</b> and also <b>/dev/sdb1</b> (a partition)</li>
</ul>

<p><b>Always select the main device</b> (the one without a number at the end):</p>
<ul>
    <li>✅ Correct: <b>/dev/disk4</b>, <b>/dev/sdb</b></li>
    <li>❌ Incorrect: <b>/dev/disk4s1</b>, <b>/dev/sdb1</b></li>
</ul>

<p>This tool will automatically create the necessary partitions on the device.</p>

<h4>Tips for identifying your SD card:</h4>
<ol>
    <li>Unplug the SD card, click Refresh</li>
    <li>Plug in the SD card, click Refresh again</li>
    <li>The newly appeared device is your SD card</li>
    <li>Check the size matches your SD card's capacity</li>
</ol>
"""
        msg_box = QtWidgets.QMessageBox()
        msg_box.setWindowTitle("Device Selection Help")
        msg_box.setTextFormat(QtCore.Qt.TextFormat.RichText)
        msg_box.setText(help_text)
        msg_box.setIcon(QtWidgets.QMessageBox.Icon.Information)
        msg_box.exec()

    def show_all_disks(self):
        """Show a dialog with all disks and allow selection"""
        logger.info("Showing all available disks")
        self.log("Loading all available disks...")
        
        # Data structure to store disk information
        all_disk_info = []
        
        try:
            if sys.platform == 'darwin':  # macOS
                # Get list of all disks using diskutil list
                output = subprocess.check_output(
                    ['diskutil', 'list'], 
                    universal_newlines=True)
                
                # Parse the output to find all disk identifiers
                current_disk = None
                for line in output.splitlines():
                    line = line.strip()
                    if line.startswith("/dev/disk"):
                        # This is a disk entry
                        parts = line.split()
                        if len(parts) >= 2:
                            disk_id = parts[0].replace("/dev/", "")
                            # Get disk info using diskutil info
                            try:
                                info_output = subprocess.check_output(
                                    ['diskutil', 'info', '-plist', disk_id],
                                    universal_newlines=True)
                                
                                # Parse plist output
                                disk_info = plistlib.loads(info_output.encode('utf-8'))
                                
                                # Extract important properties
                                device_path = f"/dev/{disk_id}"
                                size_bytes = disk_info.get('TotalSize', 0)
                                size_gb = size_bytes / (1024 * 1024 * 1024)  # Convert to GB
                                is_internal = disk_info.get('Internal', True)
                                is_removable = disk_info.get('RemovableMedia', False)
                                disk_name = disk_info.get('VolumeName', 'NO NAME')
                                
                                # Create display info
                                disk_type = "INTERNAL" if is_internal else "EXTERNAL"
                                removable = "REMOVABLE" if is_removable else "FIXED"
                                
                                display_text = f"{disk_type} {removable}: {disk_name} ({size_gb:.1f} GB) - {device_path}"
                                all_disk_info.append({
                                    "display_text": display_text,
                                    "device_path": device_path,
                                    "is_internal": is_internal,
                                    "is_removable": is_removable,
                                    "size_gb": size_gb
                                })
                                
                                logger.debug(f"Found disk: {display_text}")
                                
                            except Exception as e:
                                logger.error(f"Error getting info for {disk_id}: {e}")
                                continue
                
                if not all_disk_info:
                    logger.warning("No disks found in diskutil output")
                    self.log("No disks found. Try using the Refresh button instead.")
                    return
                    
            elif sys.platform.startswith('linux'):  # Linux
                # Use lsblk to get all disks
                output = subprocess.check_output(
                    ['lsblk', '-o', 'NAME,SIZE,RM,TYPE', '-n', '-p'], 
                    universal_newlines=True)
                
                for line in output.strip().split('\n'):
                    parts = line.split()
                    if len(parts) >= 4 and parts[3] == 'disk':
                        device_path = parts[0]
                        size = parts[1]
                        is_removable = parts[2] == '1'
                        
                        disk_type = "REMOVABLE" if is_removable else "FIXED"
                        display_text = f"{disk_type}: {device_path} ({size})"
                        
                        all_disk_info.append({
                            "display_text": display_text,
                            "device_path": device_path,
                            "is_internal": not is_removable,
                            "is_removable": is_removable,
                            "size_gb": 0  # Size parsing would need to be implemented for Linux
                        })
            
            # Create a dialog to display and select from the list of disks
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("All Available Disks")
            dialog.setMinimumSize(700, 500)
            
            layout = QtWidgets.QVBoxLayout(dialog)
            
            # Add a warning message
            warning = QtWidgets.QLabel(
                "<h3>⚠️ WARNING: Be extremely careful when selecting a disk ⚠️</h3>" +
                "<p>Selecting the wrong disk could result in <b>DATA LOSS</b>.</p>" +
                "<p>For an SD card, look for an <b>EXTERNAL REMOVABLE</b> disk.</p>" +
                "<p>Never select an <b>INTERNAL</b> disk - this is likely your system drive!</p>"
            )
            warning.setStyleSheet("color: red; font-weight: bold;")
            warning.setWordWrap(True)
            layout.addWidget(warning)
            
            # Create a table to display the disk information
            table = QtWidgets.QTableWidget()
            table.setColumnCount(5)
            table.setHorizontalHeaderLabels(["Disk", "Type", "Removable", "Size", "Select"])
            table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
            table.setRowCount(len(all_disk_info))
            
            # Add disk info to the table
            for i, disk in enumerate(all_disk_info):
                # Disk info cell
                info_item = QtWidgets.QTableWidgetItem(disk["display_text"])
                info_item.setFlags(info_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                table.setItem(i, 0, info_item)
                
                # Type cell
                type_item = QtWidgets.QTableWidgetItem("INTERNAL" if disk["is_internal"] else "EXTERNAL")
                type_item.setFlags(type_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                if disk["is_internal"]:
                    type_item.setBackground(QtGui.QColor(255, 200, 200))  # Light red for internal
                else:
                    type_item.setBackground(QtGui.QColor(200, 255, 200))  # Light green for external
                table.setItem(i, 1, type_item)
                
                # Removable cell
                removable_item = QtWidgets.QTableWidgetItem("YES" if disk["is_removable"] else "NO")
                removable_item.setFlags(removable_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                if disk["is_removable"]:
                    removable_item.setBackground(QtGui.QColor(200, 255, 200))  # Light green for removable
                else:
                    removable_item.setBackground(QtGui.QColor(255, 200, 200))  # Light red for fixed
                table.setItem(i, 2, removable_item)
                
                # Size cell
                size_text = f"{disk['size_gb']:.1f} GB" if disk['size_gb'] > 0 else "N/A"
                size_item = QtWidgets.QTableWidgetItem(size_text)
                size_item.setFlags(size_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                table.setItem(i, 3, size_item)
                
                # Select button cell
                select_btn = QtWidgets.QPushButton("Select")
                select_btn.clicked.connect(lambda checked, path=disk["device_path"]: self.select_disk_from_dialog(dialog, path))
                if disk["is_internal"]:
                    select_btn.setStyleSheet("background-color: red; color: white;")
                    select_btn.setToolTip("WARNING: This appears to be an internal disk!")
                table.setCellWidget(i, 4, select_btn)
            
            layout.addWidget(table)
            
            # Add a close button
            close_btn = QtWidgets.QPushButton("Close")
            close_btn.clicked.connect(dialog.reject)
            layout.addWidget(close_btn)
            
            dialog.exec()
            
        except Exception as e:
            logger.error(f"Error showing all disks: {e}")
            self.log(f"Error showing all disks: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to show disks: {str(e)}\n\nTry using the Refresh button instead."
            )

    def select_disk_from_dialog(self, dialog, device_path):
        """Select a disk from the dialog and add it to the device combo box"""
        # Confirmation dialog for safety
        confirm = QtWidgets.QMessageBox.warning(
            dialog,
            "Confirm Device Selection",
            f"Are you sure you want to select {device_path}?\n\n"
            "WARNING: Selecting the wrong device could result in DATA LOSS!",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No
        )
        
        if confirm == QtWidgets.QMessageBox.StandardButton.Yes:
            # Add the device to the combo box
            self.device_combo.clear()
            display_text = f"SELECTED: {device_path}"
            self.device_combo.addItem(display_text, device_path)
            self.log(f"Selected device: {device_path}")
            dialog.accept()  # Close the dialog


if __name__ == "__main__":
    logger.info("Application starting.")
    app = QtWidgets.QApplication(sys.argv)
    window = FlashTool()
    window.show()
    logger.info("Entering main application event loop.")
    exit_code = app.exec()
    logger.info("Application exiting with code %d.", exit_code)
    sys.exit(exit_code)
