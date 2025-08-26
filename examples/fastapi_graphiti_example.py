"""
FastAPI Example using GraphitiRAGAnything integration.

This example shows how to create REST API endpoints using the
GraphitiIntegrator and GraphitiRAGService components.
"""

import asyncio
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

# Ensure the project root is in the path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "python-api"))

# Import the integration components (mock if not available)
try:
    from app.integration.graphiti_integrator import GraphitiIntegrator, GraphitiIntegrationConfig
    from app.services.graphiti_rag_service import GraphitiRAGService
    from app.models.common import OperationResult
    from app.models.queries import QueryRequest, QueryResponse
    from app.models.documents import DocumentProcessingResult
    INTEGRATION_AVAILABLE = True
except ImportError:
    INTEGRATION_AVAILABLE = False
    GraphitiIntegrator = None
    GraphitiRAGService = None


# API Models
class QueryRequestModel(BaseModel):
    query: str
    mode: str = "hybrid"
    top_k: int = 10
    group_id: Optional[str] = None


class TextProcessingRequest(BaseModel):
    text: str
    title: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    group_id: Optional[str] = None


class BackendSwitchRequest(BaseModel):
    backend_type: str


# Create FastAPI app
app = FastAPI(
    title="RAG-Anything + Graphiti API",
    description="REST API for the GraphitiRAGAnything integration",
    version="1.0.0"
)

# Global service instance
graphiti_service: Optional[GraphitiRAGService] = None


async def setup_dummy_models():
    """Setup dummy model functions for testing"""
    async def dummy_llm_func(prompt: str, **kwargs) -> str:
        return f"Mock LLM response to: {prompt[:50]}..."
    
    async def dummy_embedding_func(texts: List[str]) -> List[List[float]]:
        return [[0.1, 0.2, 0.3] * 100 for _ in texts]
    
    async def dummy_vision_func(image_path: str, prompt: str) -> str:
        return f"Mock vision analysis of {image_path}"
    
    return dummy_llm_func, dummy_embedding_func, dummy_vision_func


@app.on_event("startup")
async def startup_event():
    """Initialize the GraphitiRAG service on startup"""
    global graphiti_service
    
    if not INTEGRATION_AVAILABLE:
        print("Warning: GraphitiRAGAnything integration not available. Running in mock mode.")
        return
    
    try:
        # Setup model functions
        llm_func, embedding_func, vision_func = await setup_dummy_models()
        
        # Create and initialize service
        graphiti_service = GraphitiRAGService()
        
        # Configuration for the service
        config = {
            "backend_type": "graphiti",  # Try Graphiti first
            "enable_fallback": True,  # Allow fallback to LightRAG
            "default_group_id": "api_default",
            "preserve_document_structure": True,
            
            # Graph configuration (adjust as needed)
            "graph_provider": "falkordb",
            "graph_host": "localhost",
            "graph_port": 6379,
            "graph_database": "api_rag_graph",
            "graph_password": None,
            
            # LLM configuration
            "llm_provider": "openai",
            "llm_model": "gpt-4o-mini",
            "llm_api_key": os.getenv("OPENAI_API_KEY"),
        }
        
        # Initialize service
        result = await graphiti_service.initialize(
            graphiti_config=config,
            llm_model_func=llm_func,
            embedding_func=embedding_func,
            vision_model_func=vision_func
        )
        
        if result.success:
            print(f"✓ GraphitiRAG service initialized: {result.message}")
        else:
            print(f"✗ Failed to initialize service: {result.message}")
            graphiti_service = None
            
    except Exception as e:
        print(f"✗ Error during startup: {e}")
        graphiti_service = None


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    global graphiti_service
    
    if graphiti_service:
        try:
            await graphiti_service.finalize()
            print("✓ GraphitiRAG service finalized")
        except Exception as e:
            print(f"✗ Error during shutdown: {e}")


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "RAG-Anything + Graphiti API",
        "version": "1.0.0",
        "integration_available": INTEGRATION_AVAILABLE,
        "service_initialized": graphiti_service is not None and graphiti_service._initialized,
        "endpoints": [
            "/health",
            "/process/text",
            "/process/file",
            "/query",
            "/stats",
            "/entities",
            "/relationships",
            "/backend/switch"
        ]
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if not graphiti_service:
        return {
            "status": "unhealthy",
            "message": "Service not initialized",
            "integration_available": INTEGRATION_AVAILABLE
        }
    
    try:
        health = await graphiti_service.integrator.rag_instance.health_check()
        return {
            "status": "healthy",
            "service_initialized": True,
            "backend_health": health
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": str(e),
            "service_initialized": graphiti_service._initialized
        }


@app.post("/process/text")
async def process_text(request: TextProcessingRequest):
    """Process text content"""
    if not graphiti_service:
        raise HTTPException(status_code=503, detail="Service not available")
    
    try:
        result = await graphiti_service.process_text_content(
            text=request.text,
            title=request.title,
            metadata=request.metadata,
            group_id=request.group_id
        )
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process/file")
async def process_file(
    file: UploadFile = File(...),
    group_id: Optional[str] = Form(None),
    enable_multimodal: bool = Form(True)
):
    """Process uploaded file"""
    if not graphiti_service:
        raise HTTPException(status_code=503, detail="Service not available")
    
    try:
        metadata = {"uploaded_via": "api", "enable_multimodal": enable_multimodal}
        
        result = await graphiti_service.process_document_file(
            file=file,
            metadata=metadata,
            group_id=group_id,
            enable_multimodal=enable_multimodal
        )
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query")
async def query_knowledge_graph(request: QueryRequestModel):
    """Query the knowledge graph"""
    if not graphiti_service:
        raise HTTPException(status_code=503, detail="Service not available")
    
    try:
        # Convert to internal query format
        from app.models.queries import QueryRequest
        
        query_request = QueryRequest(
            query=request.query,
            mode=request.mode,
            top_k=request.top_k,
            metadata={"group_filter": request.group_id} if request.group_id else None
        )
        
        result = await graphiti_service.execute_query(
            query_request=query_request,
            group_id=request.group_id
        )
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats(group_id: Optional[str] = None):
    """Get knowledge graph statistics"""
    if not graphiti_service:
        raise HTTPException(status_code=503, detail="Service not available")
    
    try:
        stats = await graphiti_service.get_knowledge_graph_stats(group_id=group_id)
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/entities")
async def get_entities(
    limit: int = 100,
    offset: int = 0,
    group_id: Optional[str] = None
):
    """Get entities from the knowledge graph"""
    if not graphiti_service:
        raise HTTPException(status_code=503, detail="Service not available")
    
    try:
        result = await graphiti_service.get_entities(
            limit=limit,
            offset=offset,
            group_id=group_id
        )
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/relationships")
async def get_relationships(
    limit: int = 100,
    offset: int = 0,
    group_id: Optional[str] = None
):
    """Get relationships from the knowledge graph"""
    if not graphiti_service:
        raise HTTPException(status_code=503, detail="Service not available")
    
    try:
        result = await graphiti_service.get_relationships(
            limit=limit,
            offset=offset,
            group_id=group_id
        )
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/backend/switch")
async def switch_backend(request: BackendSwitchRequest):
    """Switch between backends"""
    if not graphiti_service:
        raise HTTPException(status_code=503, detail="Service not available")
    
    try:
        result = await graphiti_service.manage_backend(
            action="switch",
            backend_type=request.backend_type
        )
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/backend/status")
async def get_backend_status():
    """Get current backend status"""
    if not graphiti_service:
        raise HTTPException(status_code=503, detail="Service not available")
    
    try:
        result = await graphiti_service.manage_backend(action="status")
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    print("Starting RAG-Anything + Graphiti API server...")
    print("Available endpoints:")
    print("  POST /process/text - Process text content")
    print("  POST /process/file - Process uploaded files") 
    print("  POST /query - Query the knowledge graph")
    print("  GET /stats - Get statistics")
    print("  GET /entities - Get entities")
    print("  GET /relationships - Get relationships")
    print("  POST /backend/switch - Switch backends")
    print("  GET /health - Health check")
    print("\nStarting server on http://localhost:8000")
    print("API docs available at http://localhost:8000/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)