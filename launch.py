# launch.py
import env_loader
import os
import gradio_app  # builds the Blocks object named `demo`

if __name__ == "__main__":
    # Choose ONE of the two lines below:

    # A) Let Gradio auto-pick a free port (recommended)
    gradio_app.demo.launch(
        server_name="127.0.0.1",
        share=True,
        show_error=True,
    )

    # B) Or force a specific port (uncomment if you prefer)
    # gradio_app.demo.launch(
    #     server_name="127.0.0.1",
    #     server_port=7861,
    #     share=False,
    #     show_error=True,
    # )
