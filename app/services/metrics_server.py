"""Simple HTTP server for Prometheus metrics endpoint."""

import asyncio
import logging
from aiohttp import web

from app.services.metrics import metrics
from app.config import settings

logger = logging.getLogger(__name__)


class MetricsServer:
    """HTTP server for exposing Prometheus metrics."""

    def __init__(self, host: str = "0.0.0.0", port: int = 9090):
        self.host = host
        self.port = port
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    async def _handle_metrics(self, request: web.Request) -> web.Response:
        """Handle /metrics endpoint."""
        try:
            metrics_text = await metrics.get_metrics()
            return web.Response(
                text=metrics_text,
                content_type="text/plain; charset=utf-8"
            )
        except Exception as e:
            logger.error(f"Error generating metrics: {e}")
            return web.Response(text="# Error generating metrics", status=500)

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Handle /health endpoint for K8s probes."""
        return web.Response(
            text='{"status": "healthy"}',
            content_type="application/json"
        )

    async def _handle_ready(self, request: web.Request) -> web.Response:
        """Handle /ready endpoint for K8s readiness probe."""
        # Check if bot is ready (could add more checks here)
        return web.Response(
            text='{"status": "ready"}',
            content_type="application/json"
        )

    async def start(self):
        """Start the metrics HTTP server."""
        self._app = web.Application()
        self._app.router.add_get("/metrics", self._handle_metrics)
        self._app.router.add_get("/health", self._handle_health)
        self._app.router.add_get("/healthz", self._handle_health)
        self._app.router.add_get("/ready", self._handle_ready)
        self._app.router.add_get("/readyz", self._handle_ready)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()

        logger.info(f"Metrics server started at http://{self.host}:{self.port}")
        logger.info(f"  - Metrics: http://{self.host}:{self.port}/metrics")
        logger.info(f"  - Health:  http://{self.host}:{self.port}/health")
        logger.info(f"  - Ready:   http://{self.host}:{self.port}/ready")

    async def stop(self):
        """Stop the metrics HTTP server."""
        if self._runner:
            await self._runner.cleanup()
            logger.info("Metrics server stopped")


# Global metrics server instance
metrics_server = MetricsServer()
