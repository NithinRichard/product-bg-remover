import streamlit as st
from PIL import Image
import io
from processor import process_product_photo

# Page configuration
st.set_page_config(
    page_title="Product Photo Studio",
    page_icon="👕",
    layout="wide"
)

# Custom CSS for premium look
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #000;
        color: white;
    }
    .stButton>button:hover {
        background-color: #333;
        color: white;
    }
    h1 {
        text-align: center;
        color: #1a1a1a;
        margin-bottom: 30px;
    }
    .status-box {
        padding: 20px;
        border-radius: 10px;
        background-color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("👕 Product Photo Background Studio")
st.markdown("### Professional background replacement for your clothing shop")

col1, col2 = st.columns([1, 1])

with col1:
    st.markdown('<div class="status-box">', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload product photo...", type=["jpg", "jpeg", "png"])
    
    manual_bg_choice = st.selectbox(
        "Background Option",
        ["Auto-detect", "White", "Black", "Realistic Studio", "Wooden Floor", "Marble Floor", "Grey Marble Floor", "Premium Dark Marble", "Premium White Marble", "Midnight Obsidian Marble", "Dark Studio (Flat Lay)", "Industrial Slate Floor", "Natural Daylight Studio", "Premium Oak Parquet"]
    )
    
    process_btn = st.button("✨ Process Photo")
    st.markdown('</div>', unsafe_allow_html=True)

    if uploaded_file is not None:
    input_image = Image.open(uploaded_file)
    
    with col1:
        st.image(input_image, caption="Original Photo", use_container_width=True)

    if process_btn:
        with st.spinner("Processing image... Removing background and detecting colors..."):
            try:
                # Prepare manual choice
                bg_map = {
                    "White": "white", 
                    "Black": "black", 
                    "Auto-detect": None,
                    "Realistic Studio": "Realistic Studio",
                    "Wooden Floor": "Wooden Floor",
                    "Marble Floor": "Marble Floor",
                    "Grey Marble Floor": "Grey Marble Floor",
                    "Premium Dark Marble": "Premium Dark Marble",
                    "Premium White Marble": "Premium White Marble",
                    "Midnight Obsidian Marble": "Midnight Obsidian Marble",
                    "Dark Studio (Flat Lay)": "Dark Studio (Flat Lay)",
                    "Industrial Slate Floor": "Industrial Slate Floor",
                    "Natural Daylight Studio": "Natural Daylight Studio",
                    "Premium Oak Parquet": "Premium Oak Parquet"
                }
                manual_bg = bg_map[manual_bg_choice]
                
                # Process
                result_img, detected_bg = process_product_photo(input_image, manual_bg)
                
                with col2:
                    st.success(f"Done! Detected product required a {detected_bg} background.")
                    st.image(result_img, caption=f"Processed Photo ({detected_bg} BG)", use_container_width=True)
                    
                    # Download button
                    buf = io.BytesIO()
                    result_img.save(buf, format="PNG")
                    byte_im = buf.getvalue()
                    
                    import os
                    base_name = os.path.splitext(uploaded_file.name)[0]
                    st.download_button(
                        label="⬇️ Download Result",
                        data=byte_im,
                        file_name=f"processed_{base_name}.png",
                        mime="image/png"
                    )
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                st.info("Tip: Make sure the image has a clear product in the foreground.")

st.markdown("---")
st.markdown("Built with ❤️ for your Instagram & Online Shop")
