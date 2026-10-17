"""Gradio web page for kh-drama-studio (for Hugging Face Spaces)."""
import tempfile
from pathlib import Path

import gradio as gr

from pipeline import run  # run(topic, scenes, out_dir) from your pipeline.py


def make_video(topic: str, scenes: int):
    if not topic or not topic.strip():
        raise gr.Error("សូមបញ្ចូលប្រធានបទ")
    out = Path(tempfile.mkdtemp())
    try:
        run(topic.strip(), int(scenes), out)
    except Exception as e:
        raise gr.Error(f"បរាជ័យ: {str(e)[:300]}")
    final = out / "final.mp4"
    if not final.exists():
        raise gr.Error("រកមិនឃើញឯកសារ final.mp4")
    return str(final)


demo = gr.Interface(
    fn=make_video,
    inputs=[
        gr.Textbox(label="ប្រធានបទរឿង", placeholder="រឿងស្នេហាក្នុងភូមិមួយ"),
        gr.Slider(1, 5, value=3, step=1, label="ចំនួនឈុត"),
    ],
    outputs=gr.Video(label="វីដេអូ"),
    title="KH Drama Studio",
)

if __name__ == "__main__":
    import os
    demo.queue(max_size=2).launch(server_name="0.0.0.0", server_port=int(os.getenv("PORT", "7860")))
