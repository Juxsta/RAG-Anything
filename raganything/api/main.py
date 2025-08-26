"""
FastAPI main application for RAG-Anything with Graphiti integration.

This module creates and configures the FastAPI application with all endpoints,
middleware, and production-ready features.
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .endpoints import (
    processing_router, querying_router, entities_router,
    communities_router, health_router, files_router, management_router
)
from .dependencies import get_rag_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TimingMiddleware(BaseHTTPMiddleware):
    """Middleware to add request timing headers."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for centralized error handling."""
    
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except HTTPException:
            # Let FastAPI handle HTTPExceptions
            raise
        except Exception as e:
            logger.error(f"Unhandled error in {request.method} {request.url}: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "error": True,
                    "message": "Internal server error",
                    "error_type": type(e).__name__,
                    "request_id": str(id(request))
                }
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting RAG-Anything API server...")
    try:
        # Initialize RAG service
        rag_service = await get_rag_service()
        logger.info("RAG service initialized successfully")
        
        # Perform health check
        health = await rag_service.health_check()
        logger.info(f"Initial health check: {health.get('status', 'unknown')}")
        
    except Exception as e:
        logger.error(f"Failed to initialize RAG service: {e}")
        # Don't fail startup - let individual requests handle the error
    
    yield
    
    # Shutdown
    logger.info("Shutting down RAG-Anything API server...")
    try:
        rag_service = await get_rag_service()
        await rag_service.finalize()
        logger.info("RAG service finalized successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


def create_app(
    title: str = "RAG-Anything API",
    description: str = "Comprehensive RAG system with Graphiti integration",
    version: str = "1.0.0",
    debug: bool = False
) -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title=title,
        description=description,
        version=version,
        debug=debug,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )
    
    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(ErrorHandlingMiddleware)
    
    # Include routers
    app.include_router(processing_router)
    app.include_router(querying_router)
    app.include_router(entities_router)
    app.include_router(communities_router)
    app.include_router(health_router)
    app.include_router(files_router)
    app.include_router(management_router)
    
    # Root endpoint
    @app.get("/")
    async def root() -> Dict[str, Any]:
        """Root endpoint with API information."""
        return {
            "name": title,
            "description": description,
            "version": version,
            "status": "operational",
            "docs_url": "/docs",
            "redoc_url": "/redoc",
            "health_check": "/health/"
        }
    
    # Health check endpoint (duplicate for load balancers)
    @app.get("/ping")
    async def ping() -> Dict[str, str]:
        """Simple ping endpoint for load balancer health checks."""
        return {"status": "ok", "message": "pong"}
    
    return app


# Create the application instance
GraphitiRAGApp = create_app(
    title="RAG-Anything with Graphiti",
    description="""
    RAG-Anything API with comprehensive Graphiti integration for multimodal document processing,
    knowledge graph management, and intelligent querying.
    
    ## Features
    - **Multimodal Processing**: Handle text, images, tables, and equations
    - **Knowledge Graphs**: Advanced graph-based knowledge representation with Graphiti
    - **Semantic Search**: Hybrid search combining vector and graph-based retrieval
    - **Episode Management**: Structured temporal knowledge with episodes
    - **Community Detection**: Automatic discovery of knowledge communities
    - **Batch Processing**: Efficient processing of multiple documents
    - **File Upload**: Direct file processing with multiple parser support
    - **Real-time Analytics**: Health monitoring and performance metrics
    
    ## Authentication
    Most endpoints support optional authentication via Bearer tokens.
    Admin endpoints require valid admin credentials.
    
    ## Rate Limiting
    API requests are rate-limited to ensure system stability.
    Contact your administrator if you need higher limits.
    """,
    version="1.0.0"
)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:GraphitiRAGApp",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )