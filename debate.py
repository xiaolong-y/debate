#!/usr/bin/env python3
"""
LLM Debate CLI - Query Claude, ChatGPT, and Gemini in parallel with synthesis.
"""

import asyncio
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.parse import quote

import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(
    name="debate",
    help="Multi-LLM debate synthesizer",
    add_completion=False,
)
console = Console()


@app.command()
def main(
    prompt: str = typer.Argument(None, help="The prompt to send to all LLMs"),
    mode: str = typer.Option(
        "synthesis",
        "--mode", "-m",
        help="Triage mode: synthesis or arbitration",
    ),
    setup: bool = typer.Option(
        False,
        "--setup",
        help="Run interactive auth setup for all LLMs",
    ),
    check: bool = typer.Option(
        False,
        "--check",
        help="Check authentication status for all LLMs",
    ),
    port: int = typer.Option(
        8765,
        "--port", "-p",
        help="Server port",
    ),
    no_browser: bool = typer.Option(
        False,
        "--no-browser",
        help="Don't open browser automatically",
    ),
):
    """
    Query Claude, ChatGPT, and Gemini in parallel and synthesize their responses.

    Examples:
        debate "Is Rust better than Go for CLI tools?"
        debate --mode arbitration "What year was Python released?"
        debate --setup  # One-time auth setup
    """
    if setup:
        asyncio.run(run_setup())
        return

    if check:
        asyncio.run(run_check())
        return

    if not prompt:
        # No prompt provided, just start the server
        console.print("[cyan]Starting debate server...[/cyan]")
        start_server_and_browser(port, no_browser)
        return

    # Start server and open browser with prompt
    start_server_and_browser(port, no_browser, prompt, mode)


async def run_setup():
    """Interactive auth setup for all LLMs."""
    from playwright_client import DebateOrchestrator

    console.print(Panel(
        "[bold]LLM Debate Auth Setup[/bold]\n\n"
        "This will open browser windows for you to log in to:\n"
        "  1. Claude (claude.ai)\n"
        "  2. ChatGPT (chatgpt.com)\n"
        "  3. Gemini (gemini.google.com)\n\n"
        "Your login sessions will be saved for future use.",
        title="Setup",
        border_style="cyan",
    ))

    async with DebateOrchestrator(headless=False) as orchestrator:
        await orchestrator.setup_all_auth()

    console.print("\n[green]Setup complete![/green] You can now run debates.")


async def run_check():
    """Check authentication status."""
    from playwright_client import DebateOrchestrator

    console.print("[cyan]Checking authentication status...[/cyan]\n")

    async with DebateOrchestrator(headless=True) as orchestrator:
        auth_status = await orchestrator.check_auth()

        for name, logged_in in auth_status.items():
            if logged_in:
                console.print(f"  [green]✓[/green] {name}: authenticated")
            else:
                console.print(f"  [red]✗[/red] {name}: not authenticated")

        all_ok = all(auth_status.values())
        if not all_ok:
            console.print("\n[yellow]Run 'debate --setup' to authenticate.[/yellow]")


def start_server_and_browser(
    port: int,
    no_browser: bool,
    prompt: str = None,
    mode: str = "synthesis",
):
    """Start the server and optionally open browser."""
    import uvicorn
    from server import app as fastapi_app

    # Build URL
    url = f"http://127.0.0.1:{port}/"
    if prompt:
        url += f"?prompt={quote(prompt)}&mode={mode}"

    console.print(f"[cyan]Starting server on port {port}...[/cyan]")

    # Open browser after short delay (in background)
    if not no_browser:
        def open_browser():
            time.sleep(1)  # Wait for server to start
            webbrowser.open(url)

        import threading
        threading.Thread(target=open_browser, daemon=True).start()

    # Start server (blocks)
    try:
        uvicorn.run(fastapi_app, host="127.0.0.1", port=port, log_level="warning")
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped.[/yellow]")


if __name__ == "__main__":
    app()
