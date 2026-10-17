"""Paste this wrapper into pipeline.py.
Rename generate_image_google to match your existing Google image function."""
from hf_image import generate_image_hf


def generate_image(prompt: str, out_path: str) -> str:
    try:
        return generate_image_google(prompt, out_path)  # your original function
    except Exception as e:
        print(f"[image] Google failed ({e}); falling back to Hugging Face")
        return generate_image_hf(prompt, out_path)
