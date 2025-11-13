#!/bin/bash

# Script to convert all image files in a folder to JPEG with 80% reduced file size
# Usage: ./convert_images.sh [input_folder] [output_folder]

# Set default folders if not provided
INPUT_FOLDER="${1:-.}"
OUTPUT_FOLDER="${2:-./converted_images}"

# Create output folder if it doesn't exist
mkdir -p "$OUTPUT_FOLDER"

# Check if ImageMagick is installed
if ! command -v convert &> /dev/null; then
    echo "Error: ImageMagick is not installed. Please install it first:"
    echo "  macOS: brew install imagemagick"
    echo "  Ubuntu/Debian: sudo apt-get install imagemagick"
    echo "  CentOS/RHEL: sudo yum install ImageMagick"
    exit 1
fi

echo "Converting images from '$INPUT_FOLDER' to '$OUTPUT_FOLDER'"
echo "Target: JPEG format with 80% file size reduction (20% quality)"
echo

# Counter for processed files
count=0

# Process common image formats
for ext in jpg jpeg png gif bmp tiff tif webp; do
    # Use find to handle case-insensitive extensions and spaces in filenames
    find "$INPUT_FOLDER" -maxdepth 1 -type f -iname "*.$ext" -print0 | while IFS= read -r -d '' file; do
        # Get filename without path and extension
        basename=$(basename "$file")
        filename="${basename%.*}"
        
        # Output filename
        output_file="$OUTPUT_FOLDER/${filename}.jpg"
        
        echo "Converting: $basename"
        
        # Convert with 20% quality (80% reduction) and optimize for file size
        if convert "$file" -quality 20 -strip -interlace Plane "$output_file"; then
            # Show file size comparison
            original_size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null)
            new_size=$(stat -f%z "$output_file" 2>/dev/null || stat -c%s "$output_file" 2>/dev/null)
            
            if [ -n "$original_size" ] && [ -n "$new_size" ]; then
                # Function to format bytes in human readable format
                format_bytes() {
                    local bytes=$1
                    if [ $bytes -ge 1048576 ]; then
                        echo "$(echo "scale=1; $bytes/1048576" | bc)MB"
                    elif [ $bytes -ge 1024 ]; then
                        echo "$(echo "scale=1; $bytes/1024" | bc)KB"
                    else
                        echo "${bytes}B"
                    fi
                }
                
                reduction=$(echo "scale=1; (1 - $new_size/$original_size) * 100" | bc -l 2>/dev/null || echo "N/A")
                echo "  Original: $(format_bytes $original_size) → New: $(format_bytes $new_size) (${reduction}% reduction)"
            fi
            
            ((count++))
        else
            echo "  Error converting $basename"
        fi
        echo
    done
done

echo "Conversion complete! Processed $count images."
echo "Output folder: $OUTPUT_FOLDER"