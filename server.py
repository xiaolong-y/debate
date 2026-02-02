"""
FastAPI server with WebSocket for real-time debate streaming.
Uses Patchright (Playwright fork with stealth) for browser automation.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

from playwright_client import DebateOrchestrator
from triage import run_triage_with_existing_client as run_triage_fn, TriageMode

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"

# Global orchestrator for connection pooling (optional optimization)
_orchestrator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    yield
    # Cleanup on shutdown
    global _orchestrator
    if _orchestrator:
        await _orchestrator.stop()
        _orchestrator = None


app = FastAPI(title="LLM Debate", lifespan=lifespan)

# Mount static files if directory exists
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    """Serve the main HTML page."""
    html_path = STATIC_DIR / "index.html"
    if html_path.exists():
        return FileResponse(html_path)
    return HTMLResponse("<h1>Static files not found</h1>", status_code=404)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "backend": "patchright"}


class WebSocketHandler:
    """Handles WebSocket communication for a debate session."""

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self._closed = False

    async def send(self, message: dict):
        """Send a JSON message to the client."""
        if not self._closed:
            try:
                await self.websocket.send_json(message)
            except Exception:
                self._closed = True

    async def send_chunk(self, source: str, content: str):
        """Send a streaming chunk."""
        await self.send({
            "type": "chunk",
            "source": source,
            "content": content,
        })

    async def send_complete(self, source: str, content: str):
        """Send completion signal with full content."""
        await self.send({
            "type": "complete",
            "source": source,
            "content": content,
        })

    async def send_status(self, message: str):
        """Send status update."""
        await self.send({
            "type": "status",
            "message": message,
        })

    async def send_error(self, source: str, message: str):
        """Send error message."""
        await self.send({
            "type": "error",
            "source": source,
            "message": message,
        })

    async def send_auth_status(self, source: str, authenticated: bool):
        """Send auth status for a specific LLM."""
        await self.send({
            "type": "auth_status",
            "source": source,
            "authenticated": authenticated,
        })


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for debate streaming.

    Client sends:
        {"action": "debate", "prompt": "...", "mode": "synthesis|arbitration"}
        {"action": "check_auth"}

    Server sends:
        {"type": "chunk", "source": "claude|chatgpt|gemini|synthesis", "content": "..."}
        {"type": "complete", "source": "...", "content": "full response"}
        {"type": "error", "source": "...", "message": "..."}
        {"type": "status", "message": "..."}
        {"type": "auth_status", "source": "...", "authenticated": bool}
    """
    await websocket.accept()
    handler = WebSocketHandler(websocket)

    try:
        while True:
            # Wait for client message
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await handler.send_error("system", "Invalid JSON")
                continue

            action = message.get("action")

            if action == "debate":
                prompt = message.get("prompt", "").strip()
                if not prompt:
                    await handler.send_error("system", "Empty prompt")
                    continue

                # Always use unified mode (combines synthesis + arbitration)
                await run_debate_session(handler, prompt, TriageMode.UNIFIED)

            elif action == "check_auth":
                await check_auth_status(handler)

            else:
                await handler.send_error("system", f"Unknown action: {action}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await handler.send_error("system", f"Server error: {str(e)[:100]}")
        except Exception:
            pass


async def run_debate_session(
    handler: WebSocketHandler,
    prompt: str,
    mode: TriageMode,
):
    """Run a full debate session with streaming updates."""
    await handler.send_status("Starting debate session...")

    orchestrator = None
    try:
        orchestrator = DebateOrchestrator(headless=False)
        await orchestrator.start()

        # Check auth first
        await handler.send_status("Checking authentication...")
        auth_status = await orchestrator.check_auth()

        for name, logged_in in auth_status.items():
            await handler.send_auth_status(name, logged_in)

        not_logged_in = [name for name, logged_in in auth_status.items() if not logged_in]
        if not_logged_in:
            await handler.send_error(
                "auth",
                f"Not logged in to: {', '.join(not_logged_in)}. Run 'debate auth' first.",
            )
            return

        await handler.send_status("Querying Claude, ChatGPT, and Gemini in parallel...")

        # Response tracking
        responses: dict[str, str] = {}

        # Async callback for streaming
        async def on_update_async(llm_name: str, chunk: str):
            await handler.send_chunk(llm_name, chunk)

        def on_update(llm_name: str, chunk: str):
            asyncio.create_task(on_update_async(llm_name, chunk))

        # Query all LLMs in parallel
        try:
            results = await orchestrator.debate(prompt, on_update=on_update, timeout=120000)
        except Exception as e:
            await handler.send_error("debate", f"Debate failed: {str(e)[:100]}")
            return

        # Send complete signals for each LLM
        for name, response in results.items():
            responses[name] = response
            await handler.send_complete(name, response)

        # Run unified triage (synthesis + arbitration in one pass)
        await handler.send_status("Running unified analysis...")

        # Use Claude client for triage (reuse existing session)
        claude_client = orchestrator.clients.get("claude")
        if not claude_client:
            await handler.send_error("triage", "Claude client not available for triage")
            return

        async def on_triage_chunk_async(chunk: str):
            await handler.send_chunk("synthesis", chunk)

        def on_triage_chunk(chunk: str):
            asyncio.create_task(on_triage_chunk_async(chunk))

        try:
            triage_result = await run_triage_fn(
                claude_client,
                prompt,
                responses,
                mode=mode,
                on_chunk=on_triage_chunk,
                timeout=120000,
            )
            await handler.send_complete("synthesis", triage_result)
        except Exception as e:
            await handler.send_error("synthesis", f"Triage failed: {str(e)[:200]}")

        await handler.send_status("Debate complete!")

    except Exception as e:
        await handler.send_error("system", f"Session error: {str(e)[:100]}")

    finally:
        # Cleanup
        if orchestrator:
            try:
                await orchestrator.stop()
            except Exception:
                pass


async def check_auth_status(handler: WebSocketHandler):
    """Check authentication status for all LLMs."""
    await handler.send_status("Checking authentication...")

    orchestrator = None
    try:
        orchestrator = DebateOrchestrator(headless=True)
        await orchestrator.start()

        auth_status = await orchestrator.check_auth()

        for name, logged_in in auth_status.items():
            await handler.send_auth_status(name, logged_in)

        all_ok = all(auth_status.values())
        if all_ok:
            await handler.send_status("All LLMs authenticated!")
        else:
            not_auth = [n for n, ok in auth_status.items() if not ok]
            await handler.send_status(f"Not authenticated: {', '.join(not_auth)}")

    except Exception as e:
        await handler.send_error("auth", f"Auth check failed: {str(e)[:100]}")

    finally:
        if orchestrator:
            try:
                await orchestrator.stop()
            except Exception:
                pass


def start_server(host: str = "127.0.0.1", port: int = 8765):
    """Start the server (for CLI use)."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)
