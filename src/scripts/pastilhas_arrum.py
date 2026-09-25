import os
from PIL import Image

# Path to the folder containing pastilha images
IMG_DIR = "imagens"  # Change to your pastilhas image path if different

def center_image(image_path):
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGBA")
            
            # Find bounding box of non-transparent content
            bbox = img.getbbox()
            if not bbox:
                return  # Empty image
            
            # Crop tightly to the content
            cropped = img.crop(bbox)
            
            # Create a new square canvas based on the largest dimension
            w, h = cropped.size
            max_dim = max(w, h)
            
            # Create transparent canvas with extra padding (10%)
            padding = int(max_dim * 0.1)
            canvas_size = max_dim + (padding * 2)
            
            new_img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
            
            # Paste the cropped content right in the center
            paste_x = (canvas_size - w) // 2
            paste_y = (canvas_size - h) // 2
            new_img.paste(cropped, (paste_x, paste_y), cropped)
            
            # Save over the original file
            new_img.save(image_path, "PNG")
            print(f"Centered: {image_path}")
            
    except Exception as e:
        print(f"Error processing {image_path}: {e}")

# Process all PNGs in directory
for root, _, files in os.walk(IMG_DIR):
    for file in files:
        if file.lower().endswith(".png"):
            center_image(os.path.join(root, file))
