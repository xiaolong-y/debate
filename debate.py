#!/usr/bin/env python3
"""
LLM Debate CLI - Query Claude, ChatGPT, and Gemini in parallel.

Two modes:
1. TURBO (default): Opens all 3 chat windows instantly (<100ms), prompt in clipboard
2. FULL: Playwright automation with response streaming and synthesis
"""

import asyncio
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.parse import quote

import typer
from rich.console import Console
from rich.panel import Panel

from config import LLMS, DEFAULT_PORT
from utils import copy_to_clipboard, open_url_native

app = typer.Typer(
    name="debate",
    help="Multi-LLM debate synthesizer - query Claude, ChatGPT, and Gemini in parallel",
    add_completion=False,
)
console = Console()


def turbo_open(prompt: str | None = None, llms: list[str] | None = None) -> None:
    """
    Open all LLM chat windows with maximum performance (<100ms).
    Prompt is copied to clipboard for easy pasting.
    """
    selected = llms or list(LLMS.keys())

    # Copy prompt to clipboard first
    if prompt:
        if copy_to_clipboard(prompt):
            console.print(f"[green]Prompt copied[/green] ({len(prompt)} chars)")
        else:
            console.print(f"[yellow]Clipboard failed[/yellow]")

    # Open all URLs in parallel
    console.print("[cyan]Opening LLM windows...[/cyan]")
    for llm in selected:
        if llm in LLMS:
            name = LLMS[llm]["name"]
            url = LLMS[llm]["new_chat_url"]
            open_url_native(url)
            console.print(f"   [green]>[/green] {name}")

    if prompt:
        console.print("\n[dim]Press Cmd+V in each chat window to paste[/dim]")


@app.command()
def go(
    prompt: str = typer.Argument(None, help="Prompt to send to all LLMs"),
    llms: str = typer.Option(
        None,
        "--llms", "-l",
        help="Comma-separated LLMs to use (default: claude,chatgpt,gemini)",
    ),
):
    """
    TURBO MODE: Open all 3 LLM chat windows instantly.

    Your prompt is copied to clipboard - just Cmd+V in each window.

    Examples:
        debate go "What is the meaning of life?"
        debate go --llms claude,chatgpt "Quick question"
    """
    llm_list = llms.split(",") if llms else None
    turbo_open(prompt, llm_list)


@app.command()
def run(
    prompt: str = typer.Argument(..., help="Prompt to send to all LLMs"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="Server port"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open browser"),
):
    """
    FULL MODE: Run with Playwright automation and response synthesis.

    Opens a web UI that streams responses from all 3 LLMs and synthesizes them.
    Slower to start but provides unified analysis.

    Examples:
        debate run "Compare React vs Vue vs Svelte"
    """
    os.environ["DEBATE_USE_PLAYWRIGHT"] = "1"
    start_server_and_browser(port, no_browser, prompt)


@app.command()
def auth():
    """
    Set up authentication for all LLMs.

    Opens browser windows for you to log in to Claude, ChatGPT, and Gemini.
    Sessions are saved for future use.
    """
    asyncio.run(run_setup())


@app.command()
def check():
    """
    Check authentication status for all LLMs.
    """
    asyncio.run(run_check())


@app.command()
def server(
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="Server port"),
):
    """
    Start the debate server without opening browser.
    """
    start_server_only(port)


@app.command()
def kill():
    """
    Kill any running debate server.
    """
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{DEFAULT_PORT}"],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                subprocess.run(["kill", "-9", pid])
            console.print(f"[green]Killed {len(pids)} process(es)[/green]")
        else:
            console.print(f"[dim]No server running on port {DEFAULT_PORT}[/dim]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    prompt: str = typer.Argument(None, help="Prompt (uses turbo mode)"),
):
    """
    Multi-LLM debate synthesizer.

    TURBO MODE (default): Opens all 3 chat windows instantly
    FULL MODE: Use 'debate run' for automation + synthesis

    Examples:
        debate "What is AI?"           # Turbo mode
        debate go "What is AI?"        # Explicit turbo mode
        debate run "What is AI?"       # Full mode with synthesis
        debate auth                    # Set up authentication
    """
    if ctx.invoked_subcommand is None:
        if prompt:
            # Default to turbo mode
            turbo_open(prompt)
        else:
            # Show help
            console.print(Panel(
                "[bold]LLM Debate[/bold] - Query Claude, ChatGPT, and Gemini\n\n"
                "[cyan]Quick start:[/cyan]\n"
                "  debate \"Your question here\"     [dim]# Opens all 3 instantly[/dim]\n\n"
                "[cyan]Commands:[/cyan]\n"
                "  debate go \"prompt\"              [dim]# Turbo mode (default)[/dim]\n"
                "  debate run \"prompt\"             [dim]# Full mode + synthesis[/dim]\n"
                "  debate auth                     [dim]# Set up login sessions[/dim]\n"
                "  debate check                    [dim]# Check auth status[/dim]\n"
                "  debate kill                     [dim]# Stop server[/dim]",
                title="Usage",
                border_style="cyan",
            ))


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

    orchestrator = DebateOrchestrator(headless=False)
    await orchestrator.start()
    await orchestrator.setup_all_auth()
    await orchestrator.stop()

    console.print("\n[green]Setup complete![/green] You can now run debates.")


async def run_check():
    """Check authentication status."""
    from playwright_client import DebateOrchestrator

    console.print("[cyan]Checking authentication status...[/cyan]\n")

    orchestrator = DebateOrchestrator(headless=True)
    await orchestrator.start()
    auth_status = await orchestrator.check_auth()
    await orchestrator.stop()

    for name, logged_in in auth_status.items():
        if logged_in:
            console.print(f"  [green]>[/green] {name}: authenticated")
        else:
            console.print(f"  [red]x[/red] {name}: not authenticated")

    if not all(auth_status.values()):
        console.print("\n[yellow]Run 'debate auth' to authenticate.[/yellow]")


def start_server_and_browser(port: int, no_browser: bool, prompt: str = None):
    """Start the server and optionally open browser."""
    import uvicorn
    from server import app as fastapi_app

    url = f"http://127.0.0.1:{port}/"
    if prompt:
        url += f"?prompt={quote(prompt)}"

    console.print(f"[cyan]Starting server on port {port}...[/cyan]")

    if not no_browser:
        def open_browser():
            time.sleep(1)
            webbrowser.open(url)

        import threading
        threading.Thread(target=open_browser, daemon=True).start()

    try:
        uvicorn.run(fastapi_app, host="127.0.0.1", port=port, log_level="warning")
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped.[/yellow]")


def start_server_only(port: int):
    """Start the server without opening browser."""
    import uvicorn
    from server import app as fastapi_app

    console.print(f"[cyan]Starting server on port {port}...[/cyan]")
    console.print(f"[dim]Open http://127.0.0.1:{port}/ in your browser[/dim]")

    try:
        uvicorn.run(fastapi_app, host="127.0.0.1", port=port, log_level="warning")
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped.[/yellow]")


if __name__ == "__main__":
    app()
