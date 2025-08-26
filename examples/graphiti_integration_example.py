"""
Example usage of RAG-Anything + Graphiti integration.

This example demonstrates how to use the new GraphitiRAGAnything class
to process documents and query the knowledge graph using either LightRAG
or Graphiti backends.
"""

import asyncio
import os
from datetime import datetime
from typing import Any, Dict, List

# Ensure the project root is in the path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from raganything import GraphitiRAGAnything, GraphitiRAGAnythingConfig, BackendType


async def setup_llm_functions():
    """
    Setup dummy LLM functions for testing.
    In production, these would be actual model implementations.
    """
    async def dummy_llm_func(prompt: str, **kwargs) -> str:
        """Dummy LLM function for testing"""
        return f"LLM Response to: {prompt[:100]}..."
    
    async def dummy_embedding_func(texts: List[str]) -> List[List[float]]:
        """Dummy embedding function for testing"""
        # Return dummy embeddings (in practice, use real embeddings)
        return [[0.1, 0.2, 0.3] * 100 for _ in texts]
    
    async def dummy_vision_func(image_path: str, prompt: str) -> str:
        """Dummy vision function for testing"""
        return f"Vision analysis of {image_path}: {prompt}"
    
    return dummy_llm_func, dummy_embedding_func, dummy_vision_func


async def test_lightrag_backend():
    """Test with LightRAG backend (fallback)"""
    print("\n=== Testing LightRAG Backend ===")
    
    # Setup model functions
    llm_func, embedding_func, vision_func = await setup_llm_functions()
    
    # Configuration for LightRAG backend
    config = GraphitiRAGAnythingConfig(
        working_dir="./test_rag_storage",
        backend_type=BackendType.LIGHTRAG,
        enable_backend_fallback=False,  # Don't fallback since we explicitly want LightRAG
        parser="mineru",
        parse_method="auto"
    )
    
    # Create integration instance
    rag_instance = GraphitiRAGAnything(
        config=config,
        llm_model_func=llm_func,
        embedding_func=embedding_func,
        vision_model_func=vision_func
    )
    
    try:
        # Initialize
        await rag_instance.initialize()
        print("✓ LightRAG backend initialized successfully")
        
        # Test text processing
        result = await rag_instance.backend.insert_text(
            "This is a test document about artificial intelligence and machine learning.",
            metadata={"source": "test", "type": "example"}
        )
        print(f"✓ Text insertion result: {result.success} - {result.message}")
        
        # Test query
        query_result = await rag_instance.query(
            "What is artificial intelligence?",
            mode="hybrid",
            top_k=5
        )
        print(f"✓ Query result: {query_result.content[:200]}...")
        
        # Get stats
        stats = await rag_instance.get_backend_stats()
        print(f"✓ Backend stats: {stats}")
        
    except Exception as e:
        print(f"✗ Error with LightRAG backend: {e}")
        
    finally:
        await rag_instance.finalize()
        print("✓ LightRAG backend finalized")


async def test_graphiti_backend():
    """Test with Graphiti backend (if available)"""
    print("\n=== Testing Graphiti Backend ===")
    
    # Setup model functions
    llm_func, embedding_func, vision_func = await setup_llm_functions()
    
    # Configuration for Graphiti backend
    config = GraphitiRAGAnythingConfig(
        working_dir="./test_graphiti_storage",
        backend_type=BackendType.GRAPHITI,
        enable_backend_fallback=True,  # Allow fallback to LightRAG
        default_group_id="test_group",
        preserve_document_structure=True,
        
        # Graphiti configuration
        graphiti_config={
            "graph_config": {
                "provider": "falkordb",
                "host": "localhost", 
                "port": 6379,
                "database": "test_rag_graph",
                "password": None
            },
            "llm_config": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "api_key": os.getenv("OPENAI_API_KEY"),
                "base_url": None
            },
            "group_id": "test_group"
        }
    )
    
    # Create integration instance
    rag_instance = GraphitiRAGAnything(
        config=config,
        llm_model_func=llm_func,
        embedding_func=embedding_func,
        vision_model_func=vision_func
    )
    
    try:
        # Initialize (may fallback to LightRAG if Graphiti unavailable)
        await rag_instance.initialize()
        actual_backend = rag_instance.backend.backend_type.value
        print(f"✓ Backend initialized: {actual_backend}")
        
        # Test multimodal content processing
        multimodal_content = {
            "title": "AI Research Paper",
            "text": "This paper explores the latest developments in artificial intelligence, "
                    "including machine learning algorithms, neural networks, and natural language processing.",
            "context": "Academic research from 2024",
            "image_caption": "Figure 1: Neural network architecture diagram showing input, hidden, and output layers"
        }
        
        result = await rag_instance.backend.insert_multimodal_content(
            multimodal_content,
            metadata={"group_id": "test_group", "document_type": "research_paper"}
        )
        print(f"✓ Multimodal content insertion: {result.success} - {result.message}")
        print(f"  Entities: {result.inserted_entities}, Relationships: {result.inserted_relationships}")
        
        # Test query
        query_result = await rag_instance.query(
            "Tell me about neural networks and machine learning",
            mode="hybrid",
            top_k=5
        )
        print(f"✓ Query executed successfully")
        print(f"  Response: {query_result.content[:300]}...")
        print(f"  Backend: {query_result.backend_type}")
        
        # Get comprehensive stats
        stats = await rag_instance.get_backend_stats()
        print(f"✓ Stats retrieved: {stats.get('backend_type', 'unknown')}")
        
        # Test health check
        health = await rag_instance.health_check()
        print(f"✓ Health check: {health.get('status', 'unknown')}")
        
    except Exception as e:
        print(f"✗ Error with Graphiti backend: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await rag_instance.finalize()
        print("✓ Backend finalized")


async def test_episode_converter():
    """Test the episode converter functionality"""
    print("\n=== Testing Episode Converter ===")
    
    from raganything import EpisodeConverter
    
    # Create converter
    converter = EpisodeConverter(
        default_group_id="test_episodes",
        preserve_document_structure=True
    )
    
    # Test content conversion
    test_content = {
        "title": "Sample Document",
        "text": "This is the main content of the document discussing various topics.",
        "image_caption": "A diagram showing the relationship between concepts",
        "table_content": "Name | Value\nAI | 95%\nML | 87%",
        "context": "Educational material from online course"
    }
    
    metadata = {
        "filename": "sample.pdf",
        "source": "test",
        "timestamp": datetime.now()
    }
    
    # Convert to episodes
    episodes = converter.convert_document(test_content, metadata)
    
    print(f"✓ Generated {len(episodes)} episodes")
    
    for i, episode in enumerate(episodes):
        print(f"  Episode {i+1}:")
        print(f"    Name: {episode.name}")
        print(f"    Type: {episode.episode_type}")
        print(f"    Content Types: {[ct.value for ct in episode.content_types]}")
        print(f"    Body: {episode.episode_body[:150]}...")
        print(f"    Tags: {episode.semantic_tags}")
        print()


async def test_backend_switching():
    """Test switching between backends"""
    print("\n=== Testing Backend Switching ===")
    
    # Setup model functions
    llm_func, embedding_func, vision_func = await setup_llm_functions()
    
    # Start with LightRAG
    config = GraphitiRAGAnythingConfig(
        working_dir="./test_switching_storage",
        backend_type=BackendType.LIGHTRAG,
        enable_backend_fallback=True
    )
    
    rag_instance = GraphitiRAGAnything(
        config=config,
        llm_model_func=llm_func,
        embedding_func=embedding_func,
        vision_model_func=vision_func
    )
    
    try:
        await rag_instance.initialize()
        print(f"✓ Started with: {rag_instance.backend.backend_type.value}")
        
        # Try to switch to Graphiti
        print("Attempting to switch to Graphiti...")
        success = await rag_instance.switch_backend(BackendType.GRAPHITI)
        
        if success:
            print(f"✓ Successfully switched to: {rag_instance.backend.backend_type.value}")
        else:
            print("✗ Failed to switch to Graphiti (may not be available)")
        
        # Switch back to LightRAG
        print("Switching back to LightRAG...")
        success = await rag_instance.switch_backend(BackendType.LIGHTRAG)
        
        if success:
            print(f"✓ Successfully switched back to: {rag_instance.backend.backend_type.value}")
        else:
            print("✗ Failed to switch back to LightRAG")
            
    except Exception as e:
        print(f"✗ Error during backend switching: {e}")
        
    finally:
        await rag_instance.finalize()


async def main():
    """Main test function"""
    print("RAG-Anything + Graphiti Integration Test")
    print("=" * 50)
    
    # Test episode converter first (no backend dependencies)
    await test_episode_converter()
    
    # Test LightRAG backend (should always work)
    await test_lightrag_backend()
    
    # Test Graphiti backend (may fallback to LightRAG)
    await test_graphiti_backend()
    
    # Test backend switching
    await test_backend_switching()
    
    print("\n" + "=" * 50)
    print("Integration testing completed!")


if __name__ == "__main__":
    # Run the tests
    asyncio.run(main())