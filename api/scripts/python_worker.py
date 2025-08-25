#!/usr/bin/env python3
"""
RAG-Anything Python Worker

This script acts as a bridge between the Node.js API server and the RAG-Anything Python module.
It communicates via stdin/stdout using JSON messages for seamless interprocess communication.
"""

import sys
import json
import os
import traceback
import asyncio
from pathlib import Path
from typing import Any, Dict, Optional, List
import logging

# Add the parent directory to Python path to import RAG-Anything
current_dir = Path(__file__).parent
parent_dir = current_dir.parent.parent
sys.path.insert(0, str(parent_dir))

try:
    from raganything import RAGAnything, RAGAnythingConfig
    from raganything.config import RAGAnythingConfig as ConfigClass
except ImportError as e:
    print(json.dumps({
        "error": {
            "code": "IMPORT_ERROR",
            "message": f"Failed to import RAG-Anything: {str(e)}",
            "details": {
                "python_path": sys.path,
                "current_dir": str(current_dir),
                "parent_dir": str(parent_dir)
            }
        }
    }), flush=True)
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)  # Log to stderr to avoid conflicts with stdout communication
    ]
)
logger = logging.getLogger(__name__)


class RAGWorker:
    """Worker class that handles RAG-Anything operations"""
    
    def __init__(self):
        self.rag_instance: Optional[RAGAnything] = None
        self.config: Optional[RAGAnythingConfig] = None
        self.initialized = False
        
    async def initialize(self, config_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Initialize the RAG-Anything instance"""
        try:
            # Create configuration
            self.config = RAGAnythingConfig()
            
            # Apply any configuration overrides
            if config_params:
                for key, value in config_params.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)
            
            # Initialize RAG-Anything instance
            self.rag_instance = RAGAnything(config=self.config)
            
            # Perform any additional setup
            if hasattr(self.rag_instance, 'initialize'):
                await self.rag_instance.initialize()
            
            self.initialized = True
            
            return {
                "success": True,
                "message": "RAG-Anything initialized successfully",
                "config": {
                    "working_dir": str(self.config.working_dir),
                    "parser": self.config.parser,
                    "parser_output_dir": str(self.config.parser_output_dir),
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG-Anything: {e}")
            return {
                "success": False,
                "error": {
                    "code": "INITIALIZATION_ERROR",
                    "message": str(e),
                    "traceback": traceback.format_exc()
                }
            }
    
    async def process_document(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single document"""
        if not self.initialized or not self.rag_instance:
            return {
                "success": False,
                "error": {
                    "code": "NOT_INITIALIZED",
                    "message": "RAG worker not initialized"
                }
            }
        
        try:
            file_path = params.get("file_path")
            doc_id = params.get("doc_id")
            options = params.get("options", {})
            
            if not file_path:
                return {
                    "success": False,
                    "error": {
                        "code": "MISSING_PARAMETER",
                        "message": "file_path is required"
                    }
                }
            
            # Process the document using RAG-Anything
            result = await self.rag_instance.aprocess_file(
                file_path=file_path,
                doc_id=doc_id,
                **options
            )
            
            return {
                "success": True,
                "result": result,
                "doc_id": doc_id,
                "file_path": file_path
            }
            
        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            return {
                "success": False,
                "error": {
                    "code": "PROCESSING_ERROR",
                    "message": str(e),
                    "traceback": traceback.format_exc()
                }
            }
    
    async def process_content_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process a pre-parsed content list"""
        if not self.initialized or not self.rag_instance:
            return {
                "success": False,
                "error": {
                    "code": "NOT_INITIALIZED",
                    "message": "RAG worker not initialized"
                }
            }
        
        try:
            content_list = params.get("content_list")
            file_path = params.get("file_path", "")
            doc_id = params.get("doc_id")
            display_stats = params.get("display_stats", True)
            
            if not content_list:
                return {
                    "success": False,
                    "error": {
                        "code": "MISSING_PARAMETER",
                        "message": "content_list is required"
                    }
                }
            
            # Process content list using RAG-Anything
            result = await self.rag_instance.aprocess_content_list(
                content_list=content_list,
                file_path=file_path,
                doc_id=doc_id,
                display_stats=display_stats
            )
            
            return {
                "success": True,
                "result": result,
                "doc_id": doc_id,
                "content_blocks": len(content_list)
            }
            
        except Exception as e:
            logger.error(f"Content list processing failed: {e}")
            return {
                "success": False,
                "error": {
                    "code": "PROCESSING_ERROR",
                    "message": str(e),
                    "traceback": traceback.format_exc()
                }
            }
    
    async def execute_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a text query"""
        if not self.initialized or not self.rag_instance:
            return {
                "success": False,
                "error": {
                    "code": "NOT_INITIALIZED",
                    "message": "RAG worker not initialized"
                }
            }
        
        try:
            query = params.get("query")
            mode = params.get("mode", "mix")
            vlm_enhanced = params.get("vlm_enhanced", False)
            
            if not query:
                return {
                    "success": False,
                    "error": {
                        "code": "MISSING_PARAMETER",
                        "message": "query is required"
                    }
                }
            
            # Execute query using RAG-Anything
            result = await self.rag_instance.aquery(
                query=query,
                mode=mode,
                vlm_enhanced=vlm_enhanced
            )
            
            return {
                "success": True,
                "result": result,
                "query": query,
                "mode": mode,
                "vlm_enhanced": vlm_enhanced
            }
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return {
                "success": False,
                "error": {
                    "code": "QUERY_ERROR",
                    "message": str(e),
                    "traceback": traceback.format_exc()
                }
            }
    
    async def execute_multimodal_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a multimodal query"""
        if not self.initialized or not self.rag_instance:
            return {
                "success": False,
                "error": {
                    "code": "NOT_INITIALIZED",
                    "message": "RAG worker not initialized"
                }
            }
        
        try:
            query = params.get("query")
            multimodal_content = params.get("multimodal_content", [])
            mode = params.get("mode", "mix")
            
            if not query:
                return {
                    "success": False,
                    "error": {
                        "code": "MISSING_PARAMETER",
                        "message": "query is required"
                    }
                }
            
            # Execute multimodal query using RAG-Anything
            result = await self.rag_instance.amultimodal_query(
                query=query,
                multimodal_content=multimodal_content,
                mode=mode
            )
            
            return {
                "success": True,
                "result": result,
                "query": query,
                "mode": mode,
                "multimodal_items": len(multimodal_content)
            }
            
        except Exception as e:
            logger.error(f"Multimodal query execution failed: {e}")
            return {
                "success": False,
                "error": {
                    "code": "MULTIMODAL_QUERY_ERROR",
                    "message": str(e),
                    "traceback": traceback.format_exc()
                }
            }
    
    async def get_status(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get system status"""
        try:
            status = {
                "initialized": self.initialized,
                "config": None,
                "storage_info": None,
                "processor_info": None
            }
            
            if self.initialized and self.rag_instance:
                # Get configuration info
                if self.config:
                    status["config"] = {
                        "working_dir": str(self.config.working_dir),
                        "parser": self.config.parser,
                        "parser_output_dir": str(self.config.parser_output_dir),
                    }
                
                # Get storage info if available
                if hasattr(self.rag_instance, 'lightrag') and self.rag_instance.lightrag:
                    # Add LightRAG storage information
                    status["storage_info"] = {
                        "lightrag_initialized": True,
                        "storage_type": "lightrag"
                    }
                
                # Get processor info if available
                if hasattr(self.rag_instance, 'modal_processors'):
                    processors = {}
                    for name, processor in self.rag_instance.modal_processors.items():
                        processors[name] = {
                            "class": processor.__class__.__name__,
                            "enabled": True
                        }
                    status["processor_info"] = processors
            
            return {
                "success": True,
                "status": status
            }
            
        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            return {
                "success": False,
                "error": {
                    "code": "STATUS_ERROR",
                    "message": str(e),
                    "traceback": traceback.format_exc()
                }
            }
    
    async def health_check(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Perform health check"""
        try:
            checks = {
                "python_process": "healthy",
                "rag_instance": "healthy" if self.initialized else "unhealthy",
                "config": "healthy" if self.config else "unhealthy"
            }
            
            # Additional health checks can be added here
            if self.initialized and self.rag_instance:
                if hasattr(self.rag_instance, 'lightrag') and self.rag_instance.lightrag:
                    checks["lightrag_storage"] = "healthy"
                else:
                    checks["lightrag_storage"] = "unhealthy"
            else:
                checks["lightrag_storage"] = "unknown"
            
            all_healthy = all(status == "healthy" for status in checks.values())
            
            return {
                "success": True,
                "health": {
                    "status": "healthy" if all_healthy else "unhealthy",
                    "checks": checks
                }
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "success": False,
                "error": {
                    "code": "HEALTH_CHECK_ERROR",
                    "message": str(e)
                }
            }
    
    async def shutdown(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Shutdown the worker"""
        try:
            if self.rag_instance and hasattr(self.rag_instance, 'cleanup'):
                await self.rag_instance.cleanup()
            
            self.initialized = False
            self.rag_instance = None
            self.config = None
            
            return {
                "success": True,
                "message": "Worker shutdown completed"
            }
            
        except Exception as e:
            logger.error(f"Shutdown failed: {e}")
            return {
                "success": False,
                "error": {
                    "code": "SHUTDOWN_ERROR",
                    "message": str(e)
                }
            }


async def main():
    """Main worker loop"""
    worker = RAGWorker()
    
    # Method mapping
    methods = {
        "initialize": worker.initialize,
        "process_document": worker.process_document,
        "process_content_list": worker.process_content_list,
        "execute_query": worker.execute_query,
        "execute_multimodal_query": worker.execute_multimodal_query,
        "get_status": worker.get_status,
        "health_check": worker.health_check,
        "shutdown": worker.shutdown
    }
    
    logger.info("RAG-Anything Python worker started")
    
    try:
        # Process messages from stdin
        for line in sys.stdin:
            try:
                # Parse incoming JSON message
                message = json.loads(line.strip())
                
                if not isinstance(message, dict):
                    raise ValueError("Message must be a JSON object")
                
                request_id = message.get("id", "unknown")
                method = message.get("method")
                params = message.get("params", {})
                
                if method not in methods:
                    response = {
                        "id": request_id,
                        "success": False,
                        "error": {
                            "code": "METHOD_NOT_FOUND",
                            "message": f"Method '{method}' not found",
                            "available_methods": list(methods.keys())
                        }
                    }
                else:
                    # Execute method
                    result = await methods[method](params)
                    response = {
                        "id": request_id,
                        **result
                    }
                
                # Send response to stdout
                print(json.dumps(response), flush=True)
                
                # Check for shutdown
                if method == "shutdown" and response.get("success"):
                    break
                    
            except json.JSONDecodeError as e:
                error_response = {
                    "id": "unknown",
                    "success": False,
                    "error": {
                        "code": "INVALID_JSON",
                        "message": f"Invalid JSON: {str(e)}"
                    }
                }
                print(json.dumps(error_response), flush=True)
                
            except Exception as e:
                logger.error(f"Unexpected error processing message: {e}")
                error_response = {
                    "id": message.get("id", "unknown") if 'message' in locals() else "unknown",
                    "success": False,
                    "error": {
                        "code": "PROCESSING_ERROR",
                        "message": str(e),
                        "traceback": traceback.format_exc()
                    }
                }
                print(json.dumps(error_response), flush=True)
    
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error(f"Worker failed: {e}")
        sys.exit(1)
    
    logger.info("RAG-Anything Python worker stopped")


if __name__ == "__main__":
    asyncio.run(main())