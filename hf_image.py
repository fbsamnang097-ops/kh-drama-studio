"""Hugging Face image generation (fallback). Uses huggingface_hub, which
routes to whichever Inference Provider currently serves the model."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from huggingface_hub import InferenceClient

HF_MODEL = os.getenv("HF_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
# Tried in order. "auto" lets HF pick; the others are explicit fallbacks.
# Override with e.g. HF_IMAGE_PROVIDERS=fal-ai,together
PROVIDERS = [p.strip() for p in os.getenv("HF_IMAGE_PROVIDERS", "auto,fal-ai,together,nebius").split(",") if p.strip()]


def generate_image_hf(prompt: str, out_path: str) -> str:
    """Generate an image via Hugging Face and save it to out_path."""
    token = os.getenv("HF_TOKEN")
    if not token:
        raise RuntimeError("Missing HF_TOKEN in environment")

    errors = []
    for provider in PROVIDERS:
        try:
            client = InferenceClient(provider=provider, api_key=token)
            image = client.text_to_image(prompt, model=HF_MODEL)  # PIL image
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            image.save(out_path)
            return out_path
        except Exception as e:
            errors.append(f"{provider}: {str(e)[:150]}")
            print(f"  [hf] provider {provider} failed: {str(e)[:150]}")

    raise RuntimeError("HF image generation failed. " + " | ".join(errors))


if __name__ == "__main__":
    print(generate_image_hf("a golden temple at sunrise, Cambodia", "test_hf.png"))
