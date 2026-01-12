import numpy as np
from PIL import Image, ImageOps, ImageFilter, ImageChops, ImageEnhance
from rembg import remove
import io
import os

def remove_background(input_image):
    """
    Removes background using rembg.
    input_image should be a PIL Image object.
    """
    img_byte_arr = io.BytesIO()
    input_image.save(img_byte_arr, format='PNG')
    input_data = img_byte_arr.getvalue()
    
    output_data = remove(input_data)
    return Image.open(io.BytesIO(output_data)).convert("RGBA")

def is_product_white(image, threshold=200):
    """
    Detects if the product is primarily white/light-colored.
    Calculates average brightness of non-transparent pixels.
    """
    # Convert to RGBA if not already
    img = image.convert("RGBA")
    # Get data as numpy array
    data = np.array(img)
    
    # Separate color and alpha channels
    rgb = data[:, :, :3]
    alpha = data[:, :, 3]
    
    # Filter only non-transparent pixels
    mask = alpha > 0
    if not np.any(mask):
        return False # Empty image
        
    pixels = rgb[mask]
    
    # Calculate average brightness (R+G+B)/3
    avg_brightness = np.mean(pixels)
    
    return avg_brightness > threshold

from PIL import ImageEnhance, ImageChops, ImageFilter

def create_drop_shadow(image, offset=(0, 0), background_color=(0, 0, 0, 100), blur=20):
    """
    Creates a drop shadow with PADDING to prevent square/clipped edges.
    """
    if "A" not in image.mode:
        return image, 0
    
    # Add large padding to give the shadow room to fade to zero
    pad = blur * 4
    w, h = image.size
    shadow_container = Image.new("RGBA", (w + pad*2, h + pad*2), (0, 0, 0, 0))
    
    # Extract alpha and blur it in the padded container
    alpha = image.split()[-1]
    shadow_mask = Image.new("L", (w + pad*2, h + pad*2), 0)
    shadow_mask.paste(alpha, (pad + offset[0], pad + offset[1]))
    
    # Apply blur
    shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(blur))
    
    # Colorize the mask
    shadow_rgba = Image.new("RGBA", shadow_mask.size, background_color)
    shadow_rgba.putalpha(shadow_mask)
    
    return shadow_rgba, pad

def create_perspective_shadow(image, scale_y=0.3, blur=15, opacity=0.5):
    """
    Creates a ground shadow by squashing the product's silhouette.
    """
    w, h = image.size
    # Create silhouette
    alpha = image.split()[-1]
    silhouette = Image.new("L", (w, h), 0)
    # Mask silhouette where product is
    silhouette.paste(255, (0, 0), mask=alpha)
    
    # Squash vertically to simulate ground perspective
    shadow_h = int(h * scale_y)
    shadow_img = silhouette.resize((w, shadow_h), Image.Resampling.LANCZOS)
    
    # Create new shadow layer
    final_shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    # Paste the squashed silhouette at the bottom area
    shadow_layer = Image.new("RGBA", (w, shadow_h), (0, 0, 0, int(255 * opacity)))
    final_shadow.paste(shadow_layer, (0, h - shadow_h), mask=shadow_img)
    
    # Blur
    final_shadow = final_shadow.filter(ImageFilter.GaussianBlur(blur))
    
    return final_shadow

def apply_rim_glow(image, color=(255, 255, 255), power=1.5, blur=10):
    """
    Creates a soft glow around the product edges to separate it from dark backgrounds.
    """
    if "A" not in image.mode:
        return image
    
    alpha = image.split()[-1]
    # Create the glow base
    glow_mask = alpha.filter(ImageFilter.GaussianBlur(blur))
    glow_color = Image.new("RGBA", image.size, color + (int(100 * power),))
    
    # Create a layer with the glow
    glow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    glow_layer.paste(glow_color, (0, 0), mask=glow_mask)
    
    # Composite: place the glow BEHIND the image
    combined = Image.new("RGBA", image.size, (0, 0, 0, 0))
    combined.paste(glow_layer, (0, 0), mask=glow_layer)
    combined.paste(image, (0, 0), mask=image)
    
    return combined

def apply_light_wrap(product, background, pos, intensity=0.15, blur=12):
    """
    Refined: Simulates multi-stage lighting wrapping for natural edge integration.
    """
    if "A" not in product.mode:
        return product
    
    p_w, p_h = product.size
    bg_crop = background.crop((pos[0], pos[1], pos[0] + p_w, pos[1] + p_h)).convert("RGBA")
    alpha = product.split()[-1]
    
    # 1. SHARP Integration (Immediate edge)
    edges_sharp = alpha.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(1))
    bg_blurred_sharp = bg_crop.filter(ImageFilter.GaussianBlur(3))
    layer_sharp = Image.new("RGBA", product.size, (0, 0, 0, 0))
    layer_sharp.paste(bg_blurred_sharp, (0, 0), mask=edges_sharp)
    
    # 2. SOFT Integration (Scene glow)
    edges_soft = alpha.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(3))
    bg_blurred_soft = bg_crop.filter(ImageFilter.GaussianBlur(blur))
    layer_soft = Image.new("RGBA", product.size, (0, 0, 0, 0))
    layer_soft.paste(bg_blurred_soft, (0, 0), mask=edges_soft)
    
    # Combine layers with product
    res = Image.alpha_composite(product, layer_sharp)
    res = Image.blend(res, Image.alpha_composite(res, layer_soft), intensity)
    
    return res

def apply_scene_shadows(product, background, pos, intensity=0.3):
    """
    ULTIMATE REALISM: Projects the background's shadows (like leaves/window gobos) 
    back onto the product so it looks like it's inside the light.
    """
    if "A" not in product.mode:
        return product
        
    p_w, p_h = product.size
    # 1. Capture the background LIGHTING pattern
    bg_crop = background.crop((pos[0], pos[1], pos[0] + p_w, pos[1] + p_h)).convert("L")
    
    # 2. Extract only the DARK parts of the background (the shadows)
    # We want to multiply these shadows onto the product
    bg_shadows = ImageOps.invert(bg_crop)
    bg_shadows = bg_shadows.filter(ImageFilter.GaussianBlur(2)) # Match scene softness
    
    # 3. Apply the captured scene shadows to the product
    rgb = product.convert("RGB")
    shadowed_rgb = ImageChops.multiply(rgb, Image.merge("RGB", (bg_shadows, bg_shadows, bg_shadows)))
    
    # Blend with original based on intensity
    blended_rgb = Image.blend(rgb, shadowed_rgb, intensity)
    
    res = product.copy()
    res.paste(blended_rgb, (0, 0), mask=product.split()[-1])
    return res

def apply_film_grain(image, intensity=0.03):
    """
    Unifies the composite by adding a microscopic layer of camera sensor noise.
    """
    rgb = image.convert("RGB")
    np_img = np.array(rgb).astype(np.float32)
    
    # Generate Gaussian noise
    noise = np.random.normal(0, intensity * 255, np_img.shape)
    np_img = np.clip(np_img + noise, 0, 255).astype(np.uint8)
    
    res = Image.fromarray(np_img)
    if "A" in image.mode:
        res = res.convert("RGBA")
        res.putalpha(image.split()[-1])
    return res

def apply_cinematic_effects(image, is_dark_bg=True, is_dark_product=False, tint_color=None):
    """
    Overhauled: RESTORES NATURAL COLORS while maintaining subtle professional depth.
    """
    processed = image
    
    # 1. Extreme Subtle Lighting Match (Tinting)
    if tint_color:
        # Reduced from 0.05 to 0.02 for maximum color "naturalness"
        processed_rgb = Image.blend(image.convert("RGB"), Image.new("RGB", image.size, tint_color), 0.02)
        if "A" in image.mode:
            processed = processed_rgb.convert("RGBA")
            processed.putalpha(image.split()[-1])
        else:
            processed = processed_rgb

    # 2. Delicate Visibility Lift for Dark Products
    if is_dark_product:
        # Reduced lift to keep blacks "Natural" and not washed out
        enhancer = ImageEnhance.Brightness(processed)
        processed = enhancer.enhance(1.1) 
        enhancer = ImageEnhance.Contrast(processed)
        processed = enhancer.enhance(1.05)
    
    # 3. Add Micro Rim Glow (Backlighting)
    if is_dark_bg:
        # Thinner (blur 5 instead of 8) to prevent 'halo' effect
        processed = apply_rim_glow(processed, color=(255, 255, 255), power=1.1, blur=5)
    
    # 4. Critical Sharpness (Keeps texture crisp)
    processed = processed.filter(ImageFilter.SHARPEN)
    
    return processed

def load_background(bg_name, target_size):
    """
    Loads a background image from assets/backgrounds and resizes it.
    """
    bg_path = os.path.join("assets", "backgrounds", f"{bg_name}.png")
    if os.path.exists(bg_path):
        bg_img = Image.open(bg_path).convert("RGBA")
        return bg_img.resize(target_size, Image.Resampling.LANCZOS)
    return Image.new("RGBA", target_size, "white")

def solidify_edges(image, iterations=2):
    """
    ULTIMATE FRINGE FIX: Expands product colors into the transparent border. 
    This ensures that semi-transparent edge pixels contain product color (black), 
    not background color (white).
    """
    if "A" not in image.mode:
        return image
        
    alpha = image.split()[-1]
    rgb = image.convert("RGB")
    
    # Simple iterative bleed: blur and mask to spread color
    for _ in range(iterations):
        # Blur the RGB part slightly
        blurred_rgb = rgb.filter(ImageFilter.GaussianBlur(3))
        # Where the original alpha is zero, we use the blurred color to "fill in"
        # This effectively bleeds the color out
        mask = alpha.point(lambda x: 255 if x == 0 else 0)
        rgb.paste(blurred_rgb, (0, 0), mask=mask)
        
    res = Image.merge("RGBA", (*rgb.split(), alpha))
    return res

def feather_edges(image, blur_radius=2):
    """
    Feathers the edges of an image by blurring its alpha mask.
    """
    if "A" not in image.mode:
        return image
    
    # 1. Solidify first to ensure no white/light fringes are introduced by the blur
    image = solidify_edges(image, iterations=2)
    
    alpha = image.split()[-1]
    # Smooth the alpha mask
    alpha = alpha.filter(ImageFilter.GaussianBlur(blur_radius))
    
    # Use the smoothed alpha
    res = image.copy()
    res.putalpha(alpha)
    return res

def create_reflection(image, opacity=0.1, blur=2):
    """
    Creates a vertically flipped, faded reflection of the product.
    """
    reflection = ImageOps.flip(image)
    w, h = reflection.size
    gradient = Image.new('L', (w, h), 0)
    for y in range(h):
        # Sharper drop-off for reflections
        alpha_val = int(255 * opacity * (1 - (y/h)**1.5))
        for x in range(w):
            gradient.putpixel((x, y), max(0, alpha_val))
    
    ref_alpha = reflection.split()[-1]
    new_alpha = ImageChops.multiply(ref_alpha, gradient)
    reflection.putalpha(new_alpha)
    reflection = reflection.filter(ImageFilter.GaussianBlur(blur))
    return reflection

def process_product_photo(input_image, manual_bg=None):
    """
    Advanced pipeline with perfect centering, sharpness preservation, and grounded shadows.
    """
    # 1. Background removal
    no_bg = remove_background(input_image)
    
    # 2. TRIM & PAD (The "Safe-Zone" Fix)
    # Trim to product silhouette to ensure perfect centering and scaling
    bbox = no_bg.getbbox()
    if bbox:
        no_bg = no_bg.crop(bbox)
    
    # Add 100px padding Safe-Zone so filters don't hit the boundary
    # This also gives room for our "Solidification" bleed
    safe_pad = 100
    orig_w, orig_h = no_bg.size
    padded_product = Image.new("RGBA", (orig_w + safe_pad*2, orig_h + safe_pad*2), (0,0,0,0))
    padded_product.paste(no_bg, (safe_pad, safe_pad))
    no_bg = padded_product

    # 3. Determine backgrounds
    image_bg_map = {
        "Realistic Studio": "studio_floor",
        "Wooden Floor": "wood_floor",
        "Marble Floor": "marble_floor",
        "Grey Marble Floor": "grey_marble_floor",
        "Premium Dark Marble": "premium_dark_marble",
        "Premium White Marble": "premium_white_marble",
        "Midnight Obsidian Marble": "obsidian_marble",
        "Dark Studio (Flat Lay)": "dark_studio_floor",
        "Industrial Slate Floor": "industrial_slate",
        "Natural Daylight Studio": "daylight_studio",
        "Premium Oak Parquet": "premium_parquet"
    }
    
    if manual_bg in image_bg_map:
        bg_key = image_bg_map[manual_bg]
        bg_layer = load_background(bg_key, no_bg.size)
        bg_w, bg_h = bg_layer.size
        
        is_floor = any(k in manual_bg for k in ["Floor", "Marble", "Studio", "Slate", "Parquet"])
        is_marble = "Marble" in manual_bg
        is_spotlight = "Obsidian" in manual_bg
        is_flat_lay = any(k in manual_bg for k in ["Flat Lay", "Daylight", "Parquet"])
        is_slate = "Slate" in manual_bg
        is_daylight = "Daylight" in manual_bg
        
        # 4. Perspective Scaling
        processed_product = no_bg
        if is_floor:
            scale_factor = 0.65 if is_flat_lay else (0.45 if is_spotlight else 0.5)
            # Use original trimmed height for accurate scaling
            target_h = int(bg_h * scale_factor)
            scale = target_h / orig_h
            processed_product = no_bg.resize((int(no_bg.size[0] * scale), int(no_bg.size[1] * scale)), Image.Resampling.LANCZOS)
        
        # 5. ADAPTIVE EDGE PURITY (Color-Aware Shave & Bleed)
        is_light_prod = is_product_white(processed_product, threshold=200)
        
        if "A" in processed_product.mode:
            mask = processed_product.split()[-1]
            # Aggressive Shave: removes ~3 pixels of original background fringe
            shrunk_mask = mask.filter(ImageFilter.MinFilter(7)) 
            processed_product.putalpha(shrunk_mask)
            
            # De-Fringe: Light-suppression (for dark products) or Clean-up (for light products)
            rgb = processed_product.convert("RGB")
            # Create a very thin edge mask to target the boundary
            edge_region = shrunk_mask.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(1))
            
            if not is_light_prod:
                # DARK PRODUCT: Darken the edges to hide "White Flicker" from the original photo
                darkened = ImageEnhance.Brightness(rgb).enhance(0.4)
                rgb.paste(darkened, (0,0), mask=edge_region)
            else:
                # LIGHT PRODUCT: Brighten/Clean the edges to hide "Dark Dirty Pixels" 
                # from an original dark background. We use iterations of solidification 
                # (handled in feather_edges) but skip the darkening pass that ruins white products.
                cleaned = ImageEnhance.Brightness(rgb).enhance(1.05) # Keep it naturally bright
                rgb.paste(cleaned, (0,0), mask=edge_region)
                
            processed_product = Image.merge("RGBA", (*rgb.split(), shrunk_mask))

        # 5b. SUBPIXEL ANTI-ALIASING (Calls Solidify internally to bleed color outward)
        processed_product = feather_edges(processed_product, blur_radius=0.4)
        
        # 7. Positioning
        p_w, p_h = processed_product.size
        pos_x = (bg_w - p_w) // 2
        pos_y = (bg_h - p_h) // 2 if (is_spotlight or is_flat_lay) else (int(bg_h * 0.7) - p_h)
        
        # 6. Apply Cinematic Effects
        avg_color = bg_layer.resize((1, 1)).getpixel((0, 0))[:3]
        is_dark_bg = any(k in manual_bg for k in ["Dark", "Obsidian", "Slate"])
        
        processed_product = apply_cinematic_effects(processed_product, 
                                                   is_dark_bg=is_dark_bg, 
                                                   is_dark_product=not is_light_prod,
                                                   tint_color=avg_color)
        
        # 6b. Scene Shadow Projection
        if is_daylight or "Parquet" in manual_bg:
            processed_product = apply_scene_shadows(processed_product, bg_layer, (pos_x, pos_y), intensity=0.08)
            
        # 6c. Advanced Light Wrap
        processed_product = apply_light_wrap(processed_product, bg_layer, (pos_x, pos_y), intensity=0.12)
        
        # 8. Render Layers
        final_render = bg_layer.copy()
        
        is_light_prod = is_product_white(processed_product, threshold=200)
        
        if is_floor:
            # 8a. Reflection/Glow (Light Bounce)
            if is_marble:
                reflection = create_reflection(processed_product, opacity=0.08, blur=4)
                final_render.paste(reflection, (pos_x, pos_y + p_h - 2), mask=reflection)
            elif is_light_prod and (is_daylight or "Parquet" in manual_bg):
                # ULTIMATE REALISM: Light Bounce
                # Light t-shirts reflect light onto the floor.
                bounce, pad_b = create_drop_shadow(processed_product, offset=(0, 0), background_color=(255,255,255,20), blur=50)
                final_render.paste(bounce, (pos_x - pad_b, pos_y - pad_b), mask=bounce)
            
            # 8b. Shadows (anchored to the bottom)
            if is_flat_lay:
                offset = (-12, 10) if (is_daylight or "Parquet" in manual_bg) else (0, 4)
                
                # ADAPTIVE OPACITY: Light products need slightly stronger shadows for contrast
                # If product is white, we increase the shadow alpha slightly (45 -> 65)
                base_op = 45 if (is_daylight or "Parquet" in manual_bg) else 80
                shadow_op = int(base_op * 1.5) if is_light_prod else base_op
                
                # Main soft shadow
                shadow_f, pad_f = create_drop_shadow(processed_product, offset=offset, background_color=(0,0,0,shadow_op), blur=35)
                final_render.paste(shadow_f, (pos_x - pad_f, pos_y - pad_f), mask=shadow_f)
                
                # ADAPTIVE CONTACT: Deeper AO for white products to fix the "floating" look
                contact_op = 220 if is_light_prod else 160
                shadow_c, pad_c = create_drop_shadow(processed_product, offset=(int(offset[0]/4), int(offset[1]/4)), background_color=(0,0,0,contact_op), blur=4)
                final_render.paste(shadow_c, (pos_x - pad_c, pos_y - pad_c), mask=shadow_c)
                
            elif is_slate:
                shadow_op = 90 if is_light_prod else 60
                shadow_s, pad_s = create_drop_shadow(processed_product, offset=(15, 12), background_color=(0,0,0,shadow_op), blur=40)
                final_render.paste(shadow_s, (pos_x - pad_s, pos_y - pad_s), mask=shadow_s)
                shadow_c, pad_c = create_drop_shadow(processed_product, offset=(3, 2), background_color=(0,0,0,200 if is_light_prod else 180), blur=4)
                final_render.paste(shadow_c, (pos_x - pad_c, pos_y - pad_c), mask=shadow_c)
            else:
                shadow_p = create_perspective_shadow(processed_product, scale_y=0.2, blur=15, opacity=0.35 if is_light_prod else 0.25)
                final_render.paste(shadow_p, (pos_x, pos_y + int(p_h * 0.1)), mask=shadow_p)
                shadow_c, pad_c = create_drop_shadow(processed_product, offset=(0, 2), background_color=(0,0,0,210 if is_light_prod else 180), blur=2)
                final_render.paste(shadow_c, (pos_x - pad_c, pos_y - pad_c), mask=shadow_c)
                shadow_s, pad_s = create_drop_shadow(processed_product, offset=(0, 4), background_color=(0,0,0,60 if is_light_prod else 40), blur=25)
                final_render.paste(shadow_s, (pos_x - pad_s, pos_y - pad_s), mask=shadow_s)
        else:
            pos_y = (bg_h - p_h) // 2
            shadow_d, pad_d = create_drop_shadow(processed_product, offset=(0, 10), background_color=(0,0,0,80 if is_light_prod else 60), blur=30)
            final_render.paste(shadow_d, (pos_x - pad_d, pos_y - pad_d), mask=shadow_d)

        final_render.paste(processed_product, (pos_x, pos_y), mask=processed_product)
        final_render = apply_film_grain(final_render, intensity=0.012)
        
        return final_render.convert("RGB"), manual_bg
    
    # Default Color Backgrounds
    bg_color = "white"
    if manual_bg and manual_bg in ["White", "Black"]:
        bg_color = manual_bg.lower()
    else:
        bg_color = "black" if is_product_white(no_bg) else "white"
        
    # Apply high-quality cleanup even for plain backgrounds
    no_bg = feather_edges(no_bg, blur_radius=0.7)
    final_render = Image.new("RGBA", no_bg.size, bg_color)
    final_render.paste(no_bg, (0, 0), mask=no_bg)
    return final_render.convert("RGB"), bg_color.capitalize()
