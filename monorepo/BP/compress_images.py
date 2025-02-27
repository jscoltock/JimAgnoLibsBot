"""
Script to compress JPEG images in a folder and save them to a 'compressed' subfolder.
Uses the Pillow library for image processing and tkinter for folder selection.

@agno: This script can be used as a utility in the Agno pipeline for image preprocessing
"""

import os
from pathlib import Path
from PIL import Image
import logging
import tkinter as tk
from tkinter import filedialog

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def select_folder() -> Path | None:
    """
    Show a folder selection dialog and return the selected path.
    
    Returns:
        Path object of selected folder or None if cancelled
    """
    # Create and hide the root window
    root = tk.Tk()
    root.withdraw()
    
    # Show folder selection dialog
    folder_path = filedialog.askdirectory(
        title='Select folder containing JPEG images',
        mustexist=True
    )
    
    # Clean up the root window
    root.destroy()
    
    return Path(folder_path) if folder_path else None

def create_compressed_folder(input_path: Path) -> Path:
    """
    Create a 'compressed' subfolder in the input directory if it doesn't exist.
    
    Args:
        input_path: Path object of the input directory
        
    Returns:
        Path object of the compressed folder
    """
    compressed_folder = input_path / 'compressed'
    compressed_folder.mkdir(exist_ok=True)
    return compressed_folder

def get_jpeg_files(input_path: Path) -> list[Path]:
    """
    Get all JPEG files from the input directory.
    
    Args:
        input_path: Path object of the input directory
        
    Returns:
        List of Path objects for JPEG files
    """
    # Look for both .jpg and .jpeg extensions (case insensitive)
    jpeg_files = []
    for ext in ('*.jpg', '*.jpeg', '*.JPG', '*.JPEG'):
        jpeg_files.extend(input_path.glob(ext))
    return jpeg_files

def compress_image(input_file: Path, output_path: Path, quality: int = 20) -> bool:
    """
    Compress a single JPEG image and save it to the output path.
    
    Args:
        input_file: Path object of the input image
        output_path: Path object of the output directory
        quality: Integer between 1-95, lower means more compression
        
    Returns:
        bool: True if compression was successful, False otherwise
    """
    try:
        # Open the image
        with Image.open(input_file) as img:
            # Prepare output path
            output_file = output_path / input_file.name
            
            # Save with compression
            img.save(
                output_file,
                'JPEG',
                optimize=True,
                quality=quality
            )
            
            # Log compression results
            original_size = input_file.stat().st_size / 1024  # KB
            compressed_size = output_file.stat().st_size / 1024  # KB
            savings = ((original_size - compressed_size) / original_size) * 100
            
            logger.info(
                f"Compressed {input_file.name}: "
                f"{original_size:.1f}KB -> {compressed_size:.1f}KB "
                f"({savings:.1f}% reduction)"
            )
            return True
            
    except Exception as e:
        logger.error(f"Error compressing {input_file.name}: {str(e)}")
        return False

def main():
    """Main function to run the image compression process."""
    # Show folder selection dialog
    input_path = select_folder()
    
    if input_path is None:
        logger.warning("No folder selected. Exiting...")
        return
    
    logger.info(f"Selected folder: {input_path}")
    
    # Create compressed folder
    compressed_folder = create_compressed_folder(input_path)
    logger.info(f"Created compressed folder at: {compressed_folder}")
    
    # Get all JPEG files
    jpeg_files = get_jpeg_files(input_path)
    
    if not jpeg_files:
        logger.warning("No JPEG files found in the selected directory!")
        return
    
    logger.info(f"Found {len(jpeg_files)} JPEG files to compress")
    
    # Process each file
    successful = 0
    for jpeg_file in jpeg_files:
        if compress_image(jpeg_file, compressed_folder):
            successful += 1
    
    # Final summary
    logger.info(f"Compression complete! Successfully compressed {successful}/{len(jpeg_files)} images")

if __name__ == "__main__":
    main() 