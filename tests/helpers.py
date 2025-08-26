"""
Test helper utilities for the RAG-Anything + Graphiti integration test suite.

This module provides utility functions, decorators, and context managers
that are commonly used across different test modules.
"""

import asyncio
import functools
import time
import tempfile
import shutil
import os
import json
import subprocess
from typing import Dict, List, Any, Optional, Callable, AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
import pytest
from unittest.mock import Mock, AsyncMock, patch
import httpx
from datetime import datetime, timedelta
import psutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from raganything.config import Config
from raganything.error_handling import ErrorHandler, RAGAnythingError
from tests.factories import TestDocument, TestEpisode, TestEntity, DocumentFactory


class TestConfig:
    """Test configuration constants"""
    
    # Timeout settings
    DEFAULT_TIMEOUT = 30.0
    SLOW_TIMEOUT = 60.0
    PERFORMANCE_TIMEOUT = 300.0
    
    # Performance thresholds
    RESPONSE_TIME_THRESHOLD = 2.0  # seconds
    MEMORY_THRESHOLD = 500  # MB
    
    # Test data limits
    MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_BATCH_SIZE = 100
    
    # API settings
    TEST_API_BASE = "http://localhost:8000"
    TEST_API_TIMEOUT = 30.0


class TimeoutError(Exception):
    """Custom timeout error for test operations"""
    pass


def timeout(seconds: float):
    """Decorator to add timeout to test functions"""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
                except asyncio.TimeoutError:
                    raise TimeoutError(f"Test function {func.__name__} timed out after {seconds} seconds")
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                def target():
                    return func(*args, **kwargs)
                
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(target)
                    try:
                        return future.result(timeout=seconds)
                    except Exception:
                        raise TimeoutError(f"Test function {func.__name__} timed out after {seconds} seconds")
            return sync_wrapper
    return decorator


def retry(max_attempts: int = 3, delay: float = 1.0, exceptions: tuple = (Exception,)):
    """Decorator to retry test operations on failure"""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                for attempt in range(max_attempts):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as e:
                        if attempt == max_attempts - 1:
                            raise
                        await asyncio.sleep(delay * (2 ** attempt))  # Exponential backoff
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                for attempt in range(max_attempts):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        if attempt == max_attempts - 1:
                            raise
                        time.sleep(delay * (2 ** attempt))  # Exponential backoff
            return sync_wrapper
    return decorator


class PerformanceMonitor:
    """Context manager for monitoring test performance"""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.start_time = None
        self.end_time = None
        self.start_memory = None
        self.peak_memory = None
        self.process = psutil.Process()
        self.monitoring = False
        self.monitor_thread = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.peak_memory = self.start_memory
        self.monitoring = True
        
        # Start memory monitoring thread
        self.monitor_thread = threading.Thread(target=self._monitor_memory, daemon=True)
        self.monitor_thread.start()
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.monitoring = False
        self.end_time = time.time()
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
    
    def _monitor_memory(self):
        """Monitor memory usage in a separate thread"""
        while self.monitoring:
            try:
                current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
                self.peak_memory = max(self.peak_memory, current_memory)
                time.sleep(0.1)  # Check every 100ms
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
    
    @property
    def duration(self) -> float:
        """Get test duration in seconds"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0
    
    @property
    def memory_increase(self) -> float:
        """Get memory increase in MB"""
        if self.start_memory and self.peak_memory:
            return self.peak_memory - self.start_memory
        return 0.0
    
    def assert_performance(self, 
                         max_duration: Optional[float] = None,
                         max_memory_mb: Optional[float] = None):
        """Assert performance metrics are within acceptable limits"""
        if max_duration and self.duration > max_duration:
            raise AssertionError(
                f"Test {self.test_name} took {self.duration:.2f}s, "
                f"exceeding limit of {max_duration}s"
            )
        
        if max_memory_mb and self.memory_increase > max_memory_mb:
            raise AssertionError(
                f"Test {self.test_name} used {self.memory_increase:.2f}MB additional memory, "
                f"exceeding limit of {max_memory_mb}MB"
            )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics as dictionary"""
        return {
            "test_name": self.test_name,
            "duration_seconds": self.duration,
            "start_memory_mb": self.start_memory,
            "peak_memory_mb": self.peak_memory,
            "memory_increase_mb": self.memory_increase
        }


@contextmanager
def temporary_directory() -> Generator[Path, None, None]:
    """Create a temporary directory for test files"""
    temp_dir = tempfile.mkdtemp(prefix="rag_test_")
    try:
        yield Path(temp_dir)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@contextmanager
def temporary_file(content: bytes = b"", suffix: str = ".txt") -> Generator[Path, None, None]:
    """Create a temporary file with content"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(content)
        temp_path = Path(f.name)
    
    try:
        yield temp_path
    finally:
        if temp_path.exists():
            temp_path.unlink()


@asynccontextmanager
async def mock_graphiti_client() -> AsyncGenerator[AsyncMock, None]:
    """Context manager for mocking Graphiti client"""
    mock_client = AsyncMock()
    
    # Mock common methods
    mock_client.add_episode.return_value = Mock(
        episode=Mock(uuid="test-episode-id"),
        nodes=[Mock(uuid=f"node-{i}") for i in range(3)],
        edges=[Mock(uuid=f"edge-{i}") for i in range(2)]
    )
    
    mock_client.search.return_value = Mock(
        nodes=[Mock(name=f"Entity {i}", summary=f"Summary {i}") for i in range(5)],
        edges=[]
    )
    
    mock_client.get_entities.return_value = [
        Mock(uuid=f"entity-{i}", name=f"Entity {i}") for i in range(10)
    ]
    
    with patch('raganything.backends.graphiti_direct.Graphiti', return_value=mock_client):
        yield mock_client


class MockHTTPClient:
    """Mock HTTP client for API testing"""
    
    def __init__(self):
        self.requests = []
        self.responses = {}
        self.default_response = httpx.Response(200, json={"status": "ok"})
    
    def set_response(self, method: str, url: str, response: httpx.Response):
        """Set a mock response for a specific method/URL combination"""
        self.responses[(method.upper(), url)] = response
    
    def set_default_response(self, response: httpx.Response):
        """Set a default response for unmatched requests"""
        self.default_response = response
    
    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Mock request method"""
        self.requests.append({
            "method": method.upper(),
            "url": url,
            "kwargs": kwargs,
            "timestamp": datetime.now()
        })
        
        key = (method.upper(), url)
        return self.responses.get(key, self.default_response)
    
    def get_requests(self, method: Optional[str] = None, url: Optional[str] = None) -> List[Dict]:
        """Get recorded requests, optionally filtered"""
        requests = self.requests
        
        if method:
            requests = [r for r in requests if r["method"] == method.upper()]
        
        if url:
            requests = [r for r in requests if r["url"] == url]
        
        return requests
    
    def assert_request_made(self, method: str, url: str, count: Optional[int] = None):
        """Assert that a specific request was made"""
        matching_requests = self.get_requests(method, url)
        
        if count is None:
            assert len(matching_requests) > 0, f"No {method} request made to {url}"
        else:
            assert len(matching_requests) == count, \
                f"Expected {count} {method} requests to {url}, got {len(matching_requests)}"


class DatabaseTestHelper:
    """Helper for database-related test operations"""
    
    @staticmethod
    @contextmanager
    def isolated_db():
        """Context manager for isolated database testing"""
        # This would typically use a test database
        # For now, we'll mock the database operations
        with patch('raganything.database.get_connection') as mock_conn:
            mock_conn.return_value = Mock()
            yield mock_conn.return_value


class GraphitiTestHelper:
    """Helper for Graphiti-specific test operations"""
    
    @staticmethod
    def create_mock_graphiti_response(
        nodes: int = 5,
        edges: int = 3,
        communities: int = 2
    ) -> Dict[str, Any]:
        """Create a mock Graphiti search response"""
        return {
            "nodes": [
                {
                    "uuid": f"node-{i}",
                    "name": f"Entity {i}",
                    "summary": f"This is entity {i} summary",
                    "entity_type": "concept" if i % 2 == 0 else "person"
                }
                for i in range(nodes)
            ],
            "edges": [
                {
                    "uuid": f"edge-{i}",
                    "source_uuid": f"node-{i}",
                    "target_uuid": f"node-{i+1}",
                    "relationship_type": "related_to",
                    "weight": 0.8
                }
                for i in range(edges)
            ],
            "communities": [
                {
                    "uuid": f"community-{i}",
                    "name": f"Community {i}",
                    "summary": f"This is community {i}",
                    "nodes": [f"node-{j}" for j in range(i*2, (i+1)*2)]
                }
                for i in range(communities)
            ]
        }
    
    @staticmethod
    def assert_episode_structure(episode_data: Dict[str, Any]):
        """Assert that episode data has the correct structure"""
        required_fields = ["name", "content", "content_type"]
        for field in required_fields:
            assert field in episode_data, f"Episode missing required field: {field}"
        
        assert isinstance(episode_data["name"], str), "Episode name must be string"
        assert isinstance(episode_data["content"], str), "Episode content must be string"
        assert episode_data["content_type"] in [
            "text", "image", "table", "equation", "code", "chart", "diagram"
        ], f"Invalid content type: {episode_data['content_type']}"


class LoadTestHelper:
    """Helper for load testing operations"""
    
    @staticmethod
    async def run_concurrent_tasks(
        tasks: List[Callable],
        max_concurrent: int = 10,
        timeout_per_task: float = 30.0
    ) -> List[Any]:
        """Run tasks concurrently with controlled concurrency"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def run_with_semaphore(task):
            async with semaphore:
                return await asyncio.wait_for(task(), timeout=timeout_per_task)
        
        return await asyncio.gather(
            *[run_with_semaphore(task) for task in tasks],
            return_exceptions=True
        )
    
    @staticmethod
    def analyze_concurrent_results(results: List[Any]) -> Dict[str, Any]:
        """Analyze results from concurrent task execution"""
        total_tasks = len(results)
        successful = sum(1 for r in results if not isinstance(r, Exception))
        failed = total_tasks - successful
        
        error_types = {}
        for result in results:
            if isinstance(result, Exception):
                error_type = type(result).__name__
                error_types[error_type] = error_types.get(error_type, 0) + 1
        
        return {
            "total_tasks": total_tasks,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total_tasks if total_tasks > 0 else 0,
            "error_types": error_types
        }


class SecurityTestHelper:
    """Helper for security testing operations"""
    
    @staticmethod
    def create_jwt_token(
        payload: Dict[str, Any],
        secret: str = "test_secret",
        algorithm: str = "HS256"
    ) -> str:
        """Create a JWT token for testing"""
        try:
            import jwt
            return jwt.encode(payload, secret, algorithm=algorithm)
        except ImportError:
            # Return a mock token if jwt not available
            import base64
            import json
            mock_payload = base64.b64encode(json.dumps(payload).encode()).decode()
            return f"mock.{mock_payload}.signature"
    
    @staticmethod
    def assert_no_sensitive_data_in_logs(log_content: str):
        """Assert that logs don't contain sensitive information"""
        sensitive_patterns = [
            "password",
            "api_key", 
            "secret",
            "token",
            "credential"
        ]
        
        log_lower = log_content.lower()
        for pattern in sensitive_patterns:
            assert pattern not in log_lower, f"Sensitive data '{pattern}' found in logs"
    
    @staticmethod
    def generate_malicious_payload(attack_type: str) -> str:
        """Generate malicious payload for security testing"""
        payloads = {
            "sql_injection": "'; DROP TABLE users; --",
            "xss": "<script>alert('XSS')</script>",
            "command_injection": "; rm -rf /",
            "path_traversal": "../../../etc/passwd"
        }
        return payloads.get(attack_type, "malicious_content")


class APITestHelper:
    """Helper for API testing operations"""
    
    @staticmethod
    async def wait_for_api_ready(
        base_url: str = TestConfig.TEST_API_BASE,
        timeout: float = 30.0,
        check_interval: float = 1.0
    ):
        """Wait for API to become ready"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{base_url}/health")
                    if response.status_code == 200:
                        return True
            except Exception:
                pass
            
            await asyncio.sleep(check_interval)
        
        raise TimeoutError(f"API at {base_url} did not become ready within {timeout} seconds")
    
    @staticmethod
    def assert_response_structure(
        response: httpx.Response,
        expected_fields: List[str],
        status_code: int = 200
    ):
        """Assert API response has expected structure"""
        assert response.status_code == status_code, \
            f"Expected status {status_code}, got {response.status_code}"
        
        try:
            data = response.json()
        except Exception:
            pytest.fail("Response is not valid JSON")
        
        for field in expected_fields:
            assert field in data, f"Response missing field: {field}"
    
    @staticmethod
    def create_multipart_file_data(document: TestDocument) -> Dict[str, Any]:
        """Create multipart file data for API testing"""
        return {
            "files": (document.filename, document.content, document.mime_type)
        }


class CacheTestHelper:
    """Helper for cache testing operations"""
    
    @staticmethod
    def assert_cache_hit_rate(
        cache_stats: Dict[str, Any],
        min_hit_rate: float = 0.8
    ):
        """Assert cache hit rate meets minimum threshold"""
        hits = cache_stats.get("hits", 0)
        misses = cache_stats.get("misses", 0)
        total_requests = hits + misses
        
        if total_requests == 0:
            pytest.skip("No cache requests to analyze")
        
        hit_rate = hits / total_requests
        assert hit_rate >= min_hit_rate, \
            f"Cache hit rate {hit_rate:.2%} below minimum {min_hit_rate:.2%}"
    
    @staticmethod
    def simulate_cache_pressure(cache, operations: int = 1000):
        """Simulate high cache pressure for testing"""
        for i in range(operations):
            key = f"test_key_{i}"
            value = f"test_value_{i}" * 100  # Make values large
            cache.set(key, value)


class TestDataManager:
    """Manager for test data lifecycle"""
    
    def __init__(self):
        self.created_documents = []
        self.created_episodes = []
        self.created_entities = []
    
    def create_test_document(self, **kwargs) -> TestDocument:
        """Create and track a test document"""
        document = DocumentFactory.create_text_document(**kwargs)
        self.created_documents.append(document)
        return document
    
    def cleanup(self):
        """Clean up all created test data"""
        # In a real implementation, this would clean up database records,
        # temporary files, etc.
        self.created_documents.clear()
        self.created_episodes.clear()
        self.created_entities.clear()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


# Utility functions for common test operations
async def wait_for_condition(
    condition: Callable[[], bool],
    timeout: float = 10.0,
    interval: float = 0.1
) -> bool:
    """Wait for a condition to become true"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if condition():
            return True
        await asyncio.sleep(interval)
    
    return False


def create_test_config(**overrides) -> Config:
    """Create a test configuration with overrides"""
    config = Config()
    
    # Apply test defaults
    test_defaults = {
        "debug": True,
        "log_level": "DEBUG",
        "cache_enabled": True,
        "cache_ttl": 300
    }
    
    # Apply defaults and then overrides
    for key, value in {**test_defaults, **overrides}.items():
        if hasattr(config, key):
            setattr(config, key, value)
    
    return config


def assert_no_exceptions_in_logs(log_records: List) -> None:
    """Assert that no exceptions are recorded in logs"""
    exception_records = [
        record for record in log_records 
        if record.levelname in ["ERROR", "CRITICAL"] or record.exc_info
    ]
    
    if exception_records:
        messages = [record.getMessage() for record in exception_records]
        pytest.fail(f"Unexpected exceptions in logs: {messages}")


def measure_execution_time(func: Callable) -> Callable:
    """Decorator to measure and store execution time"""
    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            result = await func(*args, **kwargs)
            execution_time = time.time() - start
            
            # Store timing in result if it's a dict
            if isinstance(result, dict):
                result["_execution_time"] = execution_time
            
            return result
        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start
            
            # Store timing in result if it's a dict
            if isinstance(result, dict):
                result["_execution_time"] = execution_time
            
            return result
        return sync_wrapper


# Test markers for different test categories
def requires_graphiti(func):
    """Mark test as requiring Graphiti backend"""
    return pytest.mark.requires_graphiti(func)


def requires_api_keys(func):
    """Mark test as requiring API keys"""
    return pytest.mark.requires_api_keys(func)


def mock_external(func):
    """Mark test as mocking external dependencies"""
    return pytest.mark.mock_external(func)


def slow_test(func):
    """Mark test as slow (for optional execution)"""
    return pytest.mark.slow(func)