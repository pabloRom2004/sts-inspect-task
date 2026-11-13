import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from inspect_ai.hooks import EvalSetEnd, EvalSetStart, Hooks, hooks


@hooks(
    name="live_viewer",
    description="Serve the active Inspect log through an authenticated Hawk relay",
)
class LiveViewer(Hooks):
    """Expose a loopback-only viewer when explicitly enabled for a Hawk smoke."""

    def __init__(self) -> None:
        """Track the viewer subprocess owned by this evaluation."""
        self.process = None

    async def on_eval_set_start(self, data: EvalSetStart) -> None:
        """Start the viewer against the actual log directory supplied by Inspect."""
        port = os.environ.get("STS_VIEWER_PORT")
        if not port:
            return
        output = Path(tempfile.gettempdir()) / "sts-inspect-viewer.log"
        with output.open("a") as stream:
            self.process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "inspect_ai",
                "view",
                "--log-dir",
                data.log_dir,
                "--host",
                "127.0.0.1",
                "--port",
                str(int(port)),
                stdout=stream,
                stderr=subprocess.STDOUT,
            )

    async def on_eval_set_end(self, data: EvalSetEnd) -> None:
        """Release the viewer process when the smoke run finishes."""
        if self.process is not None:
            self.process.terminate()
            await asyncio.wait_for(self.process.wait(), timeout=10)
            self.process = None
