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
import urllib.request  # Add import for URL handling
import stat  # Import for file permissions
import tempfile  # Import for temporary directory handling

def setup_logging():
    """Set up logging with proper directory handling"""
    try:
        # Use a temporary directory for logs if we can't write to the preferred location
        if sys.platform == 'darwin':
            # Try to use ~/Library/Logs first
            preferred_logs_dir = os.path.expanduser('~/Library/Logs/PicoCalc-SD-Flasher')
            try:
                os.makedirs(preferred_logs_dir, mode=0o700, exist_ok=True)
                logs_dir = preferred_logs_dir
            except (OSError, IOError):
                # Fall back to temporary directory
                logs_dir = os.path.join(tempfile.gettempdir(), 'PicoCalc-SD-Flasher-Logs')
                os.makedirs(logs_dir, mode=0o700, exist_ok=True)
        else:
            # On other platforms, use ~/.picocalc-sd-flasher/logs/
            logs_dir = os.path.expanduser('~/.picocalc-sd-flasher/logs')
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

# Official PicoCalc firmware images from GitHub repository
OFFICIAL_FIRMWARE_IMAGES = {
    "FUZIX": {
        "name": "FUZIX OS",
        "description": "Lightweight UNIX-like OS for minimal resource usage",
        "path": "PicoCalc_FUZIX_v1.0.uf2",
        "url": "https://raw.githubusercontent.com/cjstoddard/PicoCalc-uf2/main/uf2/fuzix.uf2"
    },
    "PicoMite": {
        "name": "PicoMite BASIC",
        "description": "BASIC language interpreter based on MMBasic",
        "path": "PicoCalc_PicoMite_v1.0.uf2",
        "url": "https://raw.githubusercontent.com/cjstoddard/PicoCalc-uf2/main/uf2/PicoMite.uf2"
    },
    "NES": {
        "name": "NES Emulator",
        "description": "NES emulator for programming study",
        "path": "PicoCalc_NES_v1.0.uf2",
        "url": "https://raw.githubusercontent.com/cjstoddard/PicoCalc-uf2/main/uf2/picocalc_nes.uf2"
    },
    "uLisp": {
        "name": "uLisp",
        "description": "Lisp programming language for ARM-based boards",
        "path": "PicoCalc_uLisp_v1.0.uf2",
        "url": "https://raw.githubusercontent.com/cjstoddard/PicoCalc-uf2/main/uf2/ulisp-arm.ino.rpipico.uf2"
    },
    "MP3Player": {
        "name": "MP3 Player",
        "description": "Simple MP3 player based on YAHAL",
        "path": "PicoCalc_MP3Player_v0.5.uf2",
        "url": "https://raw.githubusercontent.com/cjstoddard/PicoCalc-uf2/main/uf2/pico-mp3-player.uf2"
    }
}

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
        
        # Add firmware download group
        download_group = QtWidgets.QGroupBox("Download Official Firmware")
        download_layout = QtWidgets.QVBoxLayout(download_group)
        
        # Add firmware list widget
        self.firmware_list = QtWidgets.QListWidget()
        self.firmware_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        
        # Populate firmware list
        for key, firmware in OFFICIAL_FIRMWARE_IMAGES.items():
            item = QtWidgets.QListWidgetItem(f"{firmware['name']}")
            item.setToolTip(firmware['description'])
            item.setData(QtCore.Qt.ItemDataRole.UserRole, key)
            self.firmware_list.addItem(item)
        
        # Add buttons in horizontal layout
        buttons_layout = QtWidgets.QHBoxLayout()
        
        # Add download button
        self.download_btn = QtWidgets.QPushButton("Download Selected Firmware")
        self.download_btn.clicked.connect(self.download_firmware)
        
        # Add download all button
        self.download_all_btn = QtWidgets.QPushButton("Download All Firmware")
        self.download_all_btn.clicked.connect(self.download_all_firmware)
        
        # Add scan GitHub button
        self.scan_github_btn = QtWidgets.QPushButton("Scan GitHub for Firmware")
        self.scan_github_btn.clicked.connect(self.scan_github_for_firmware)
        
        buttons_layout.addWidget(self.download_btn)
        buttons_layout.addWidget(self.download_all_btn)
        buttons_layout.addWidget(self.scan_github_btn)
        
        download_layout.addWidget(self.firmware_list)
        download_layout.addLayout(buttons_layout)
        layout.addWidget(download_group)
        
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
        self.log_output.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.WidgetWidth)
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
        layout.setStretch(3, 1)  # Make log output take available space
        
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

    def select_firmware(self):
        """Open file dialog to select firmware image"""
        logger.info("Opening firmware selection dialog.")
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Firmware Image",
            "",
            "Firmware Files (*.uf2);;All Files (*)",
        )

        if file_path:
            self.firmware_path = file_path
            self.firmware_label.setText(os.path.basename(file_path))
            logger.info("User selected firmware: %s", file_path)
            self.log(f"Selected firmware: {file_path}")
        else:
            logger.info("Firmware selection cancelled by user.")
            
    def _check_url_exists(self, url):
        """Check if a URL exists and is accessible"""
        try:
            headers = {'User-Agent': 'PicoCalc-SD-Flasher/1.0'}
            req = urllib.request.Request(url, headers=headers, method='HEAD')
            with urllib.request.urlopen(req, timeout=5) as response:
                return True
        except Exception:
            return False
            
    def download_firmware(self):
        """Download selected firmware from GitHub repository"""
        current_item = self.firmware_list.currentItem()
        if not current_item:
            self.log("Please select a firmware to download")
            return
            
        # Get firmware info - could be a key or a dictionary depending on selection source
        firmware_data = current_item.data(QtCore.Qt.ItemDataRole.UserRole)
        
        # Handle different firmware_info formats
        if isinstance(firmware_data, str):
            # This is a key from the predefined list
            firmware_info = OFFICIAL_FIRMWARE_IMAGES[firmware_data]
        else:
            # This is a firmware_info dictionary from the GitHub scan
            firmware_info = firmware_data
        
        # Add attribution message
        self.log("Community firmware files from https://github.com/cjstoddard/PicoCalc-uf2")
        
        # Check if URL exists before starting download
        if not self._check_url_exists(firmware_info['url']):
            self.log(f"Warning: The firmware URL seems to be unavailable: {firmware_info['url']}")
            
            # Show error dialog with option to open GitHub
            msg_box = QtWidgets.QMessageBox()
            msg_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("Firmware URL Unavailable")
            msg_box.setText(f"The firmware URL appears to be unavailable:\n{firmware_info['url']}")
            msg_box.setInformativeText("Would you like to try anyway or open the GitHub repository in your browser to find the firmware manually?")
            
            try_anyway_btn = msg_box.addButton("Try Download Anyway", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
            open_github_btn = msg_box.addButton("Open GitHub Repository", QtWidgets.QMessageBox.ButtonRole.ActionRole)
            cancel_btn = msg_box.addButton(QtWidgets.QMessageBox.StandardButton.Cancel)
            
            msg_box.exec()
            
            if msg_box.clickedButton() == open_github_btn:
                self.open_github_repo()
                return
            elif msg_box.clickedButton() == cancel_btn:
                return
            # If they clicked Try Anyway, we continue with the download
        
        # Update status
        self.log(f"Downloading {firmware_info['name']}...")
        self.update_progress(0, f"Downloading {firmware_info['name']}")
        
        try:
            # Create downloads directory if it doesn't exist
            downloads_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "downloads")
            os.makedirs(downloads_dir, exist_ok=True)
            
            # Use the direct URL from the firmware_info dictionary
            download_url = firmware_info['url']
            
            # Start download in a separate thread to avoid blocking UI
            download_thread = threading.Thread(
                target=self._download_firmware_thread,
                args=(download_url, downloads_dir, firmware_info)
            )
            download_thread.daemon = True
            download_thread.start()
            
        except Exception as e:
            logger.error("Error starting download: %s", e, exc_info=True)
            self.log(f"Error starting download: {str(e)}")
            self.update_progress(0, "Download failed")

    def _download_firmware_thread(self, url, download_dir, firmware_info):
        """Handle firmware download in a separate thread"""
        try:
            # Download with progress tracking
            local_filename = os.path.join(download_dir, firmware_info['path'])
            logger.info(f"Attempting to download from: {url}")
            logger.info(f"Target save location: {local_filename}")
            
            # Add a user agent to avoid some GitHub API restrictions
            headers = {'User-Agent': 'PicoCalc-SD-Flasher/1.0'}
            req = urllib.request.Request(url, headers=headers)
            
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    file_size = int(response.headers.get('Content-Length', 0))
                    
                    if file_size == 0:
                        raise ValueError("File size is 0 or Content-Length header is missing")
                    
                    with open(local_filename, 'wb') as f:
                        downloaded = 0
                        block_size = 8192
                        
                        while True:
                            buffer = response.read(block_size)
                            if not buffer:
                                break
                                
                            downloaded += len(buffer)
                            f.write(buffer)
                            
                            # Update progress - use QueuedConnection to safely update from another thread
                            progress = int((downloaded / file_size) * 100) if file_size > 0 else 0
                            status_msg = f"Downloading: {progress}%"
                            
                            # Use the signal/slot mechanism for thread-safe UI updates
                            QtCore.QMetaObject.invokeMethod(
                                self, 
                                "update_progress_from_thread", 
                                QtCore.Qt.ConnectionType.QueuedConnection,
                                QtCore.Q_ARG(int, progress),
                                QtCore.Q_ARG(str, status_msg)
                            )
                
                # Verify file was downloaded and has content
                if os.path.getsize(local_filename) == 0:
                    raise ValueError("Downloaded file is empty")
                    
                # Update UI when complete
                QtCore.QMetaObject.invokeMethod(
                    self,
                    "download_complete",
                    QtCore.Qt.ConnectionType.QueuedConnection,
                    QtCore.Q_ARG(str, local_filename)
                )
                
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    error_msg = f"Firmware file not found (404). The URL may be incorrect: {url}"
                else:
                    error_msg = f"HTTP Error {e.code}: {e.reason}"
                logger.error(error_msg)
                QtCore.QMetaObject.invokeMethod(
                    self,
                    "download_error",
                    QtCore.Qt.ConnectionType.QueuedConnection,
                    QtCore.Q_ARG(str, error_msg)
                )
            except urllib.error.URLError as e:
                error_msg = f"Network error: {str(e.reason)}. Please check your internet connection."
                logger.error(error_msg)
                QtCore.QMetaObject.invokeMethod(
                    self,
                    "download_error",
                    QtCore.Qt.ConnectionType.QueuedConnection,
                    QtCore.Q_ARG(str, error_msg)
                )
            except TimeoutError:
                error_msg = "Download timed out. Server may be slow or unavailable."
                logger.error(error_msg)
                QtCore.QMetaObject.invokeMethod(
                    self,
                    "download_error",
                    QtCore.Qt.ConnectionType.QueuedConnection,
                    QtCore.Q_ARG(str, error_msg)
                )
                
        except Exception as e:
            logger.error("Download error: %s", e, exc_info=True)
            # Update UI on error
            QtCore.QMetaObject.invokeMethod(
                self,
                "download_error",
                QtCore.Qt.ConnectionType.QueuedConnection,
                QtCore.Q_ARG(str, str(e))
            )
            
    @QtCore.pyqtSlot(int, str)
    def update_progress_from_thread(self, value, status):
        """Thread-safe method to update progress from background threads"""
        self.update_progress(value, status)

    @QtCore.pyqtSlot(str)
    def download_complete(self, filename):
        """Handle download completion in the main thread"""
        self.log(f"Download completed: {filename}")
        self.update_progress(100, "Download completed")
        self.firmware_path = filename
        self.firmware_label.setText(os.path.basename(filename))

    @QtCore.pyqtSlot(str)
    def download_error(self, error_msg):
        """Handle download error in the main thread"""
        self.log(f"Download failed: {error_msg}")
        self.update_progress(0, "Download failed")
        
        # Show error dialog with option to open GitHub
        msg_box = QtWidgets.QMessageBox()
        msg_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("Download Failed")
        msg_box.setText(f"Failed to download firmware:\n{error_msg}")
        msg_box.setInformativeText("Would you like to open the GitHub repository in your browser instead?")
        msg_box.setStandardButtons(
            QtWidgets.QMessageBox.StandardButton.Yes | 
            QtWidgets.QMessageBox.StandardButton.No
        )
        msg_box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Yes)
        
        if msg_box.exec() == QtWidgets.QMessageBox.StandardButton.Yes:
            self.open_github_repo()
            
    def open_github_repo(self):
        """Open the GitHub repository in the default web browser"""
        try:
            import webbrowser
            # Direct link to the firmware directory
            repo_url = "https://github.com/cjstoddard/PicoCalc-uf2"
            self.log(f"Opening GitHub firmware repository in browser: {repo_url}")
            webbrowser.open(repo_url)
        except Exception as e:
            logger.error("Failed to open browser: %s", e, exc_info=True)
            self.log(f"Failed to open browser: {str(e)}")

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
        
        # Check if any REQUIRED validation failed
        # (Fix: Only fail on required checks that actually failed, ignore pending ones like partition alignment)
        required_failed = any(
            not success for check, (success, _) in validation_results.items() 
            if check in ["device", "partition_sequence", "formatting", "dd_write"]
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

            # Step 3: Flashing firmware
            linux_partition = validator.get_partition_device(device, 2)
            logger.info("Step 3: Flashing firmware to %s", linux_partition)
            self.update_progress(50, "Flashing firmware")
            self.log(f"Flashing firmware '{os.path.basename(self.firmware_path)}' to {linux_partition}...")
            
            # Unmount the specific partition before flashing
            if sys.platform == 'darwin':
                self.log(f"Unmounting target partition {linux_partition}...")
                self.run_command(f"diskutil unmount {linux_partition}", check_return_code=False)
            
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
            # Use a smaller block size (1m instead of 4M) which is more compatible on macOS
            cmd = f"sudo dd if='{source}' of='{target}' bs=1m"
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

    def scan_github_for_firmware(self):
        """Display the list of available firmware images"""
        logger.info("Showing available firmware images")
        self.log("Loading available firmware images...")
        self.log("Using community firmware source: https://github.com/cjstoddard/PicoCalc-uf2")
        
        # Use the predefined firmware images list
        available_firmware = []
        for key, fw in OFFICIAL_FIRMWARE_IMAGES.items():
            available_firmware.append(fw)
            
        # Clear the firmware list
        self.firmware_list.clear()
        
        # Add each firmware to the list
        for firmware in available_firmware:
            item = QtWidgets.QListWidgetItem(firmware['name'])
            item.setToolTip(firmware['description'])
            item.setData(QtCore.Qt.ItemDataRole.UserRole, firmware)
            self.firmware_list.addItem(item)
            
        self.log(f"Found {len(available_firmware)} firmware files.")
        self.update_progress(100, "Ready to download")
        
        # Select the first item by default
        if self.firmware_list.count() > 0:
            self.firmware_list.setCurrentRow(0)

    def download_all_firmware(self):
        """Download all available firmware images to the downloads folder"""
        logger.info("Starting batch download of all firmware images")
        self.log("Starting download of all firmware images...")
        self.log("Community firmware files from https://github.com/cjstoddard/PicoCalc-uf2")
        
        # Create downloads directory if it doesn't exist
        downloads_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "downloads")
        os.makedirs(downloads_dir, exist_ok=True)
        
        # Get list of firmware to download
        firmware_list = list(OFFICIAL_FIRMWARE_IMAGES.values())
        total_count = len(firmware_list)
        
        # Start the batch download in a separate thread
        download_thread = threading.Thread(
            target=self._batch_download_thread,
            args=(firmware_list, downloads_dir)
        )
        download_thread.daemon = True
        download_thread.start()
        
    def _batch_download_thread(self, firmware_list, downloads_dir):
        """Download multiple firmware files in sequence"""
        total_count = len(firmware_list)
        successful_downloads = 0
        failed_downloads = 0
        
        for i, firmware in enumerate(firmware_list):
            try:
                # Update progress
                progress = int((i / total_count) * 100)
                QtCore.QMetaObject.invokeMethod(
                    self, 
                    "update_progress_from_thread", 
                    QtCore.Qt.ConnectionType.QueuedConnection,
                    QtCore.Q_ARG(int, progress),
                    QtCore.Q_ARG(str, f"Downloading {firmware['name']} ({i+1}/{total_count})")
                )
                
                # Log the download attempt
                msg = f"Downloading {firmware['name']} ({i+1}/{total_count}): {firmware['url']}"
                logger.info(msg)
                QtCore.QMetaObject.invokeMethod(
                    self, 
                    "log_from_thread", 
                    QtCore.Qt.ConnectionType.QueuedConnection,
                    QtCore.Q_ARG(str, msg)
                )
                
                # Perform the download
                local_filename = os.path.join(downloads_dir, firmware['path'])
                headers = {'User-Agent': 'PicoCalc-SD-Flasher/1.0'}
                req = urllib.request.Request(firmware['url'], headers=headers)
                
                with urllib.request.urlopen(req, timeout=30) as response:
                    with open(local_filename, 'wb') as f:
                        f.write(response.read())
                
                # Check if file was downloaded successfully
                if os.path.exists(local_filename) and os.path.getsize(local_filename) > 0:
                    successful_downloads += 1
                    success_msg = f"Successfully downloaded {firmware['name']} to {local_filename}"
                    logger.info(success_msg)
                    QtCore.QMetaObject.invokeMethod(
                        self, 
                        "log_from_thread", 
                        QtCore.Qt.ConnectionType.QueuedConnection,
                        QtCore.Q_ARG(str, success_msg)
                    )
                else:
                    failed_downloads += 1
                    error_msg = f"Downloaded file {firmware['name']} is empty or missing"
                    logger.error(error_msg)
                    QtCore.QMetaObject.invokeMethod(
                        self, 
                        "log_from_thread", 
                        QtCore.Qt.ConnectionType.QueuedConnection,
                        QtCore.Q_ARG(str, error_msg)
                    )
                    
            except Exception as e:
                failed_downloads += 1
                error_msg = f"Failed to download {firmware['name']}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                QtCore.QMetaObject.invokeMethod(
                    self, 
                    "log_from_thread", 
                    QtCore.Qt.ConnectionType.QueuedConnection,
                    QtCore.Q_ARG(str, error_msg)
                )
                
        # Final update with summary
        summary = f"Download complete: {successful_downloads} successful, {failed_downloads} failed"
        logger.info(summary)
        QtCore.QMetaObject.invokeMethod(
            self, 
            "log_from_thread", 
            QtCore.Qt.ConnectionType.QueuedConnection,
            QtCore.Q_ARG(str, summary)
        )
        
        # Update progress to 100%
        QtCore.QMetaObject.invokeMethod(
            self, 
            "update_progress_from_thread", 
            QtCore.Qt.ConnectionType.QueuedConnection,
            QtCore.Q_ARG(int, 100),
            QtCore.Q_ARG(str, "Download complete")
        )
        
        # Open the downloads folder if there were successful downloads
        if successful_downloads > 0:
            QtCore.QMetaObject.invokeMethod(
                self, 
                "open_downloads_folder", 
                QtCore.Qt.ConnectionType.QueuedConnection
            )
            
    @QtCore.pyqtSlot(str)
    def log_from_thread(self, message):
        """Thread-safe method to log messages from background threads"""
        self.log(message)
        
    @QtCore.pyqtSlot()
    def open_downloads_folder(self):
        """Open the downloads folder in the file explorer"""
        try:
            downloads_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "downloads")
            if sys.platform == 'darwin':  # macOS
                subprocess.run(['open', downloads_dir])
            elif sys.platform.startswith('linux'):  # Linux
                subprocess.run(['xdg-open', downloads_dir])
            elif sys.platform == 'win32':  # Windows
                subprocess.run(['explorer', downloads_dir])
        except Exception as e:
            logger.error("Error opening downloads folder: %s", e, exc_info=True)
            self.log(f"Error opening downloads folder: {str(e)}")

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
                # Get list of all disks
                output = subprocess.check_output(
                    ['diskutil', 'list'], 
                    universal_newlines=True)
                
                # Parse the output to find all disk identifiers
                disk_identifiers = []
                for line in output.splitlines():
                    if line.startswith("/dev/disk") and not "s" in line.split()[0]:
                        disk_id = line.split()[0].replace("/dev/", "")
                        disk_identifiers.append(disk_id)
                
                # Get detailed info for each disk
                for disk_id in disk_identifiers:
                    try:
                        info_output = subprocess.check_output(
                            ['diskutil', 'info', disk_id],
                            universal_newlines=True)
                        
                        # Extract important properties
                        device_path = f"/dev/{disk_id}"
                        size_gb = "Unknown"
                        is_internal = True
                        is_removable = False
                        disk_name = "Unknown"
                        
                        # Parse the output for key properties
                        for line in info_output.splitlines():
                            if "Disk Size:" in line:
                                try:
                                    size_parts = line.split("(")
                                    if len(size_parts) > 1:
                                        gb_part = size_parts[1].split()
                                        size_gb = gb_part[0]
                                except Exception:
                                    pass
                            elif "Device / Media Name:" in line:
                                try:
                                    disk_name = line.split("Device / Media Name:")[1].strip()
                                except Exception:
                                    pass
                            elif "Internal:" in line:
                                is_internal = "Yes" in line
                            elif "Removable Media:" in line:
                                is_removable = "Yes" in line or "Removable" in line
                        
                        # Create display info
                        disk_type = "INTERNAL" if is_internal else "EXTERNAL"
                        removable = "REMOVABLE" if is_removable else "FIXED"
                        
                        display_text = f"{disk_type} {removable}: {disk_name} ({size_gb}) - {device_path}"
                        all_disk_info.append({
                            "display_text": display_text,
                            "device_path": device_path,
                            "is_internal": is_internal,
                            "is_removable": is_removable
                        })
                        
                    except Exception as e:
                        logger.error(f"Error getting info for {disk_id}: {e}")
                        
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
                            "is_removable": is_removable
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
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(["Disk", "Type", "Removable", "Select"])
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
                
                # Select button cell
                select_btn = QtWidgets.QPushButton("Select")
                select_btn.clicked.connect(lambda checked, path=disk["device_path"]: self.select_disk_from_dialog(dialog, path))
                if disk["is_internal"]:
                    select_btn.setStyleSheet("background-color: red; color: white;")
                    select_btn.setToolTip("WARNING: This appears to be an internal disk!")
                table.setCellWidget(i, 3, select_btn)
            
            layout.addWidget(table)
            
            # Add a close button
            close_btn = QtWidgets.QPushButton("Close")
            close_btn.clicked.connect(dialog.reject)
            layout.addWidget(close_btn)
            
            dialog.exec()
            
        except Exception as e:
            logger.error(f"Error showing all disks: {e}")
            self.log(f"Error showing all disks: {str(e)}")
            
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
