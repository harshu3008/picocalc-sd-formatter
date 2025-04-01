#!/usr/bin/env python3

import os
import re
import subprocess
from typing import List, Dict, Tuple, Optional
import logging
import sys

logger = logging.getLogger(__name__)

class SDCardValidator:
    def __init__(self):
        # Platform-specific device patterns
        if sys.platform == 'darwin':  # macOS
            self.device_pattern = re.compile(r'^/dev/disk[0-9]+$')
            self.partition_pattern = re.compile(r'^/dev/disk[0-9]+s[0-9]+$')
        else:  # Linux
            self.device_pattern = re.compile(r'^/dev/(?:sd[a-z]|nvme[0-9]+n[0-9]+)$')
            self.partition_pattern = re.compile(r'^/dev/(?:sd[a-z][0-9]+|nvme[0-9]+n[0-9]+p[0-9]+)$')
        
    def get_partition_device(self, device: str, partition_num: int) -> str:
        """Get platform-specific partition device name"""
        if sys.platform == 'darwin':  # macOS
            return f"{device}s{partition_num}"
        else:  # Linux
            if 'nvme' in device:
                return f"{device}p{partition_num}"
            return f"{device}{partition_num}"
        
    def validate_device(self, device: str) -> Tuple[bool, str]:
        """Validate device path and existence"""
        if not self.device_pattern.match(device):
            return False, f"Invalid device path format: {device}. Expected format for {sys.platform}: {self.device_pattern.pattern}"
            
        if not os.path.exists(device):
            return False, f"Device does not exist: {device}"
            
        # Check if device is removable
        try:
            if sys.platform == 'darwin':  # macOS
                disk_id = os.path.basename(device)
                # Use plist format for reliable parsing
                result = subprocess.run(
                    ['diskutil', 'info', '-plist', disk_id], 
                    capture_output=True, text=True, check=True
                )
                
                # Parse plist output for more reliable data extraction
                import plistlib
                disk_info = plistlib.loads(result.stdout.encode('utf-8'))
                
                # Check if removable using plist keys
                if not (disk_info.get('RemovableMedia', False) or 
                        disk_info.get('Removable', False) or 
                        disk_info.get('External', False)):
                    return False, f"Device {device} is not removable or external"
                    
            elif sys.platform.startswith('linux'):  # Linux
                # Use -d for device only, -o for output format, -n for no headers
                result = subprocess.run(
                    ['lsblk', '-d', '-o', 'NAME,RM', '-n', device], 
                    capture_output=True, text=True, check=True
                )
                
                # Parse lsblk output - second column should be "1" for removable
                if not result.stdout.strip() or "1" not in result.stdout.split():
                    return False, f"Device {device} is not removable"
            else:
                return False, f"Unsupported platform: {sys.platform}"
                
        except subprocess.CalledProcessError as e:
            return False, f"Failed to check device: {str(e)}"
        except Exception as e:
            return False, f"Failed to check device removability: {str(e)}"
            
        return True, "Device validation passed"

    def validate_partition_sequence(self, device: str, total_size_mb: int) -> List[str]:
        """Generate and validate the exact partition sequence"""
        fat_size = total_size_mb - 32
        return [
            f"parted -s {device} mklabel msdos",
            f"parted -s {device} mkpart primary fat32 1MiB {fat_size}MiB",
            f"parted -s {device} mkpart primary {fat_size}MiB 100%"
        ]

    def validate_formatting_flags(self, partition: str, fs_type: str) -> Tuple[bool, str]:
        """Validate formatting flags for each partition"""
        if fs_type == 'fat32':
            try:
                if sys.platform == 'darwin':  # macOS
                    # Check for newfs_msdos which is macOS equivalent of mkfs.fat
                    result = subprocess.run(['which', 'newfs_msdos'], 
                                         capture_output=True, text=True, check=False)
                    if result.returncode != 0:
                        return False, "newfs_msdos not found on macOS"
                    return True, "macOS FAT32 formatting tool available"
                else:  # Linux
                    # First check if mkfs.fat exists
                    result = subprocess.run(['which', 'mkfs.fat'], 
                                         capture_output=True, text=True, check=False)
                    if result.returncode != 0:
                        return False, "mkfs.fat not found"
                        
                    # Then check for specific flags
                    # Rather than parsing stdout which might vary, check for help output
                    # that includes the required flags
                    result = subprocess.run(['mkfs.fat', '--help'], 
                                         capture_output=True, text=True, check=False)
                    
                    if result.returncode != 0:
                        return False, "Failed to check mkfs.fat options"
                        
                    required_flags = ['-F', '-v', '-I']
                    missing_flags = []
                    
                    for flag in required_flags:
                        if flag not in result.stdout:
                            missing_flags.append(flag)
                    
                    if missing_flags:
                        return False, f"Required FAT32 formatting flags not available: {', '.join(missing_flags)}"
                    
                    return True, "FAT32 formatting flags validation passed"
            except FileNotFoundError as e:
                return False, f"Formatting tool not found: {str(e)}"
            except Exception as e:
                return False, f"Failed to validate formatting flags: {str(e)}"
                
        return True, "Formatting flags validation passed"

    def validate_partition_alignment(self, device: str) -> Tuple[bool, str]:
        """Validate 32MB partition alignment"""
        try:
            partition_device = self.get_partition_device(device, 2)
            
            if sys.platform == 'darwin':  # macOS
                # Run diskutil info with plist output for reliable parsing
                result = subprocess.run(
                    ['diskutil', 'info', '-plist', partition_device], 
                    capture_output=True, text=True, check=True
                )
                
                import plistlib
                disk_info = plistlib.loads(result.stdout.encode('utf-8'))
                
                # Get partition offset and check alignment
                offset_bytes = disk_info.get('Offset', 0)
                # 32MB alignment in bytes
                alignment_bytes = 32 * 1024 * 1024
                
                if offset_bytes % alignment_bytes != 0:
                    return False, f"Partition not aligned to 32MB boundary (offset: {offset_bytes})"
            else:  # Linux
                # Use better sectors calculation
                result = subprocess.run(['fdisk', '-l', device], capture_output=True, text=True, check=True)
                
                # Get sector size
                sector_size = 512  # Default sector size
                for line in result.stdout.split('\n'):
                    if "Sector size" in line:
                        try:
                            sector_size = int(line.split(':')[1].split()[0])
                            break
                        except (IndexError, ValueError):
                            pass
                
                # Calculate alignment in sectors (32MB / sector_size)
                alignment_sectors = (32 * 1024 * 1024) // sector_size
                
                # Extract start sector of second partition
                for line in result.stdout.split('\n'):
                    if device + '2' in line or self.get_partition_device(device, 2) in line:
                        try:
                            parts = line.split()
                            # Find the start sector column (usually 2nd or 3rd)
                            for i, part in enumerate(parts):
                                if part.isdigit() and i > 0:
                                    start_sector = int(part)
                                    if start_sector % alignment_sectors != 0:
                                        return False, f"Second partition not aligned to 32MB boundary (sector: {start_sector}, alignment: {alignment_sectors})"
                                    break
                        except (IndexError, ValueError) as e:
                            return False, f"Failed to parse partition info: {str(e)}"
            
            # Check partition size is exactly 32MB
            size_mb = self.get_partition_size_mb(self.get_partition_device(device, 2))
            if abs(size_mb - 32) > 1:  # Allow 1MB tolerance
                return False, f"Linux partition size is {size_mb:.2f}MB, expected 32MB"
                
            return True, "Partition alignment validation passed"
        except subprocess.CalledProcessError as e:
            return False, f"Failed to get partition information: {str(e)}"
        except Exception as e:
            return False, f"Failed to validate partition alignment: {str(e)}"
            
    def get_partition_size_mb(self, partition_device: str) -> float:
        """Get partition size in MB"""
        try:
            if sys.platform == 'darwin':  # macOS
                result = subprocess.run(
                    ['diskutil', 'info', '-plist', partition_device], 
                    capture_output=True, text=True, check=True
                )
                
                import plistlib
                disk_info = plistlib.loads(result.stdout.encode('utf-8'))
                size_bytes = disk_info.get('Size', 0)
                
            else:  # Linux
                result = subprocess.run(
                    ['lsblk', '--bytes', '--output', 'SIZE', '--noheadings', partition_device], 
                    capture_output=True, text=True, check=True
                )
                size_bytes = int(result.stdout.strip())
                
            return size_bytes / (1024 * 1024)  # Convert to MB
            
        except Exception as e:
            logger.error(f"Failed to get partition size: {str(e)}")
            return 0

    def validate_dd_write(self, source: str, target_device: str, partition_num: int) -> Tuple[bool, str]:
        """Validate dd write command for second partition"""
        if not os.path.exists(source):
            return False, f"Source file does not exist: {source}"
        
        target = self.get_partition_device(target_device, partition_num)
        
        if not self.partition_pattern.match(target):
            return False, f"Invalid target partition format: {target}"
        
        # Verify disk exists    
        if not os.path.exists(target_device):
            return False, f"Target device does not exist: {target_device}"
            
        return True, "DD write validation passed"

    def validate_all(self, device: str, total_size_mb: int, firmware_path: str) -> Dict[str, Tuple[bool, str]]:
        """Run all validations and return results"""
        # First check device
        device_result = self.validate_device(device)
        
        # Generate and check partition sequence
        partition_result = (False, "Partition sequence not validated")
        try:
            commands = self.validate_partition_sequence(device, total_size_mb)
            if len(commands) != 3:
                partition_result = (False, "Invalid partition command count generated")
            elif not commands[0].endswith("mklabel msdos"):
                partition_result = (False, "First command must create MSDOS label")
            elif "mkpart primary fat32" not in commands[1]:
                partition_result = (False, "Second command must create FAT32 partition")
            elif "mkpart primary" not in commands[2]:
                partition_result = (False, "Third command must create Linux partition")
            else:
                # Calculate correct size
                fat_size = total_size_mb - 32
                if f"{fat_size}MiB" not in commands[1]:
                    partition_result = (False, f"FAT32 partition must end at {fat_size}MiB")
                else:
                    partition_result = (True, "Partition sequence validated")
        except Exception as e:
            partition_result = (False, f"Failed to validate partition sequence: {str(e)}")
        
        # Get formatting flags validation
        formatting_result = self.validate_formatting_flags(self.get_partition_device(device, 1), 'fat32')
        
        # Check alignment
        alignment_result = self.validate_partition_alignment(device)
        
        # Validate DD write
        dd_result = self.validate_dd_write(firmware_path, device, 2)
        
        # Return all results
        results = {
            "device": device_result,
            "partition_sequence": partition_result,
            "formatting": formatting_result,
            "alignment": alignment_result,
            "dd_write": dd_result
        }
        return results

def format_validation_results(results: Dict[str, Tuple[bool, str]]) -> str:
    """Format validation results for display"""
    output = []
    for check, (success, message) in results.items():
        status = "✓" if success else "✗"
        output.append(f"{status} {check}: {message}")
    return "\n".join(output) 