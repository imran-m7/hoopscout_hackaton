"""The step names a job shows while it runs (real pipeline and demo mode use the same ones)."""
STEPS = {
    "shooting": ["Converting video", "Detecting pose", "Finding shots", "Drawing video", "Saving results"],
    "dribbling": ["Converting video", "Detecting pose", "Tracking ball", "Counting dribbles",
                  "Drawing video", "Saving results"],
    "jump": ["Converting video", "Detecting pose", "Finding jumps", "Drawing video", "Saving results"],
}
