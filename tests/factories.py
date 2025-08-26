"""
Test data factories for generating realistic test data across all test suites.

This module provides factory functions for creating test data that matches the
expected formats for the RAG-Anything + Graphiti integration system.
"""

import uuid
import random
import string
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from faker import Faker
from dataclasses import dataclass
import base64
import io
from PIL import Image
import pandas as pd

fake = Faker()

# Content type mappings for episode generation
CONTENT_TYPES = [
    "text", "image", "table", "equation", "code", "chart",
    "diagram", "audio_transcript", "video_transcript"
]

MIME_TYPES = {
    "pdf": "application/pdf",
    "txt": "text/plain",
    "md": "text/markdown", 
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "jpg": "image/jpeg",
    "png": "image/png",
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
}


@dataclass
class TestDocument:
    """Represents a test document for upload testing"""
    filename: str
    content: bytes
    mime_type: str
    size: int
    metadata: Dict[str, Any]


@dataclass 
class TestEpisode:
    """Represents a test episode for Graphiti testing"""
    name: str
    content: str
    content_type: str
    metadata: Dict[str, Any]
    uuid: Optional[str] = None


@dataclass
class TestEntity:
    """Represents a test entity from Graphiti"""
    uuid: str
    name: str
    entity_type: str
    summary: str
    metadata: Dict[str, Any]


@dataclass
class TestRelationship:
    """Represents a test relationship between entities"""
    uuid: str
    source_uuid: str
    target_uuid: str
    relationship_type: str
    weight: float
    metadata: Dict[str, Any]


@dataclass
class TestUser:
    """Represents a test user for authentication testing"""
    user_id: str
    username: str
    email: str
    api_key: str
    permissions: List[str]
    created_at: datetime
    is_active: bool = True


class DocumentFactory:
    """Factory for generating test documents"""
    
    @staticmethod
    def create_text_document(
        filename: Optional[str] = None,
        content: Optional[str] = None,
        size: Optional[int] = None
    ) -> TestDocument:
        """Create a test text document"""
        if not filename:
            filename = f"{fake.slug()}.txt"
        
        if not content:
            if size:
                # Generate content of specific size
                content = fake.text(max_nb_chars=size)
            else:
                content = "\n".join([fake.paragraph() for _ in range(random.randint(3, 10))])
        
        content_bytes = content.encode('utf-8')
        
        return TestDocument(
            filename=filename,
            content=content_bytes,
            mime_type="text/plain",
            size=len(content_bytes),
            metadata={
                "author": fake.name(),
                "created_at": fake.date_time_between(start_date='-1y', end_date='now').isoformat(),
                "language": "en",
                "word_count": len(content.split())
            }
        )
    
    @staticmethod
    def create_pdf_document(filename: Optional[str] = None) -> TestDocument:
        """Create a mock PDF document"""
        if not filename:
            filename = f"{fake.slug()}.pdf"
        
        # Create minimal PDF content (header only)
        pdf_content = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        
        return TestDocument(
            filename=filename,
            content=pdf_content,
            mime_type="application/pdf",
            size=len(pdf_content),
            metadata={
                "author": fake.name(),
                "title": fake.sentence(),
                "created_at": fake.date_time_between(start_date='-1y', end_date='now').isoformat(),
                "page_count": random.randint(1, 100)
            }
        )
    
    @staticmethod
    def create_image_document(
        filename: Optional[str] = None,
        width: int = 100,
        height: int = 100
    ) -> TestDocument:
        """Create a test image document"""
        if not filename:
            filename = f"{fake.slug()}.png"
        
        # Create a simple test image
        img = Image.new('RGB', (width, height), color=(random.randint(0, 255), 
                                                       random.randint(0, 255), 
                                                       random.randint(0, 255)))
        
        # Convert to bytes
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_bytes = img_buffer.getvalue()
        
        return TestDocument(
            filename=filename,
            content=img_bytes,
            mime_type="image/png",
            size=len(img_bytes),
            metadata={
                "width": width,
                "height": height,
                "format": "PNG",
                "created_at": fake.date_time_between(start_date='-1y', end_date='now').isoformat()
            }
        )
    
    @staticmethod
    def create_csv_document(
        filename: Optional[str] = None,
        rows: int = 10,
        columns: int = 5
    ) -> TestDocument:
        """Create a test CSV document"""
        if not filename:
            filename = f"{fake.slug()}.csv"
        
        # Generate random data
        data = {}
        for i in range(columns):
            col_name = fake.word().capitalize()
            if i == 0:
                data[col_name] = [fake.name() for _ in range(rows)]
            elif i == 1:
                data[col_name] = [fake.email() for _ in range(rows)]
            elif i == 2:
                data[col_name] = [fake.random_int(min=18, max=80) for _ in range(rows)]
            else:
                data[col_name] = [fake.sentence() for _ in range(rows)]
        
        df = pd.DataFrame(data)
        csv_content = df.to_csv(index=False).encode('utf-8')
        
        return TestDocument(
            filename=filename,
            content=csv_content,
            mime_type="text/csv",
            size=len(csv_content),
            metadata={
                "rows": rows,
                "columns": columns,
                "created_at": fake.date_time_between(start_date='-1y', end_date='now').isoformat()
            }
        )
    
    @staticmethod
    def create_large_document(size_mb: int = 10) -> TestDocument:
        """Create a large test document for performance testing"""
        target_size = size_mb * 1024 * 1024  # Convert to bytes
        content_chunks = []
        current_size = 0
        
        while current_size < target_size:
            chunk = fake.text(max_nb_chars=10000)
            content_chunks.append(chunk)
            current_size += len(chunk.encode('utf-8'))
        
        content = "\n".join(content_chunks)
        content_bytes = content.encode('utf-8')
        
        return TestDocument(
            filename=f"large_document_{size_mb}mb.txt",
            content=content_bytes,
            mime_type="text/plain",
            size=len(content_bytes),
            metadata={
                "size_mb": size_mb,
                "author": fake.name(),
                "created_at": fake.date_time_between(start_date='-1y', end_date='now').isoformat()
            }
        )


class EpisodeFactory:
    """Factory for generating test episodes"""
    
    @staticmethod
    def create_text_episode(
        name: Optional[str] = None,
        content: Optional[str] = None
    ) -> TestEpisode:
        """Create a text episode"""
        if not name:
            name = f"Text: {fake.sentence()}"
        
        if not content:
            content = "\n".join([fake.paragraph() for _ in range(random.randint(2, 5))])
        
        return TestEpisode(
            name=name,
            content=content,
            content_type="text",
            metadata={
                "word_count": len(content.split()),
                "created_at": datetime.now().isoformat(),
                "source": "test_factory"
            },
            uuid=str(uuid.uuid4())
        )
    
    @staticmethod
    def create_image_episode(name: Optional[str] = None) -> TestEpisode:
        """Create an image episode"""
        if not name:
            name = f"Image: {fake.sentence()}"
        
        # Create base64 encoded image data
        img = Image.new('RGB', (100, 100), color='blue')
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_b64 = base64.b64encode(img_buffer.getvalue()).decode()
        
        return TestEpisode(
            name=name,
            content=f"data:image/png;base64,{img_b64}",
            content_type="image",
            metadata={
                "format": "PNG",
                "dimensions": "100x100",
                "created_at": datetime.now().isoformat(),
                "source": "test_factory"
            },
            uuid=str(uuid.uuid4())
        )
    
    @staticmethod
    def create_table_episode(
        name: Optional[str] = None,
        rows: int = 5,
        columns: int = 3
    ) -> TestEpisode:
        """Create a table episode"""
        if not name:
            name = f"Table: {fake.sentence()}"
        
        # Generate table HTML
        headers = [fake.word().capitalize() for _ in range(columns)]
        table_html = "<table><thead><tr>"
        for header in headers:
            table_html += f"<th>{header}</th>"
        table_html += "</tr></thead><tbody>"
        
        for _ in range(rows):
            table_html += "<tr>"
            for _ in range(columns):
                table_html += f"<td>{fake.word()}</td>"
            table_html += "</tr>"
        
        table_html += "</tbody></table>"
        
        return TestEpisode(
            name=name,
            content=table_html,
            content_type="table",
            metadata={
                "rows": rows,
                "columns": columns,
                "format": "HTML",
                "created_at": datetime.now().isoformat(),
                "source": "test_factory"
            },
            uuid=str(uuid.uuid4())
        )
    
    @staticmethod
    def create_code_episode(
        name: Optional[str] = None,
        language: str = "python"
    ) -> TestEpisode:
        """Create a code episode"""
        if not name:
            name = f"Code: {fake.sentence()}"
        
        code_samples = {
            "python": '''
def fibonacci(n):
    """Calculate fibonacci number"""
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

# Example usage
for i in range(10):
    print(f"fib({i}) = {fibonacci(i)}")
            '''.strip(),
            
            "javascript": '''
function factorial(n) {
    // Calculate factorial
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

// Example usage
console.log(`5! = ${factorial(5)}`);
            '''.strip(),
            
            "sql": '''
SELECT u.name, u.email, COUNT(o.id) as order_count
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE u.created_at >= DATE_SUB(NOW(), INTERVAL 1 YEAR)
GROUP BY u.id
ORDER BY order_count DESC
LIMIT 10;
            '''.strip()
        }
        
        content = code_samples.get(language, code_samples["python"])
        
        return TestEpisode(
            name=name,
            content=content,
            content_type="code",
            metadata={
                "language": language,
                "line_count": len(content.split('\n')),
                "created_at": datetime.now().isoformat(),
                "source": "test_factory"
            },
            uuid=str(uuid.uuid4())
        )
    
    @staticmethod
    def create_batch_episodes(count: int = 10) -> List[TestEpisode]:
        """Create a batch of mixed episode types"""
        episodes = []
        
        for _ in range(count):
            episode_type = random.choice(["text", "image", "table", "code"])
            
            if episode_type == "text":
                episodes.append(EpisodeFactory.create_text_episode())
            elif episode_type == "image":
                episodes.append(EpisodeFactory.create_image_episode())
            elif episode_type == "table":
                episodes.append(EpisodeFactory.create_table_episode())
            elif episode_type == "code":
                lang = random.choice(["python", "javascript", "sql"])
                episodes.append(EpisodeFactory.create_code_episode(language=lang))
        
        return episodes


class EntityFactory:
    """Factory for generating test entities"""
    
    @staticmethod
    def create_person_entity() -> TestEntity:
        """Create a person entity"""
        name = fake.name()
        return TestEntity(
            uuid=str(uuid.uuid4()),
            name=name,
            entity_type="person",
            summary=f"{name} is a {fake.job()} at {fake.company()}. {fake.sentence()}",
            metadata={
                "occupation": fake.job(),
                "company": fake.company(),
                "email": fake.email(),
                "created_at": datetime.now().isoformat()
            }
        )
    
    @staticmethod
    def create_organization_entity() -> TestEntity:
        """Create an organization entity"""
        company = fake.company()
        return TestEntity(
            uuid=str(uuid.uuid4()),
            name=company,
            entity_type="organization",
            summary=f"{company} is a {fake.bs()} company. {fake.catch_phrase()}",
            metadata={
                "industry": fake.bs(),
                "founded": fake.date_between(start_date='-50y', end_date='-5y').year,
                "website": fake.url(),
                "created_at": datetime.now().isoformat()
            }
        )
    
    @staticmethod
    def create_concept_entity() -> TestEntity:
        """Create a concept entity"""
        concept = fake.word().title()
        return TestEntity(
            uuid=str(uuid.uuid4()),
            name=concept,
            entity_type="concept",
            summary=f"{concept} is an important concept related to {fake.bs()}. {fake.sentence()}",
            metadata={
                "domain": fake.bs(),
                "complexity": random.choice(["low", "medium", "high"]),
                "created_at": datetime.now().isoformat()
            }
        )
    
    @staticmethod
    def create_location_entity() -> TestEntity:
        """Create a location entity"""
        city = fake.city()
        return TestEntity(
            uuid=str(uuid.uuid4()),
            name=city,
            entity_type="location",
            summary=f"{city} is a city in {fake.country()}. {fake.sentence()}",
            metadata={
                "country": fake.country(),
                "population": fake.random_int(min=1000, max=10000000),
                "coordinates": {"lat": float(fake.latitude()), "lng": float(fake.longitude())},
                "created_at": datetime.now().isoformat()
            }
        )
    
    @staticmethod
    def create_entity_batch(count: int = 20) -> List[TestEntity]:
        """Create a batch of mixed entities"""
        entities = []
        entity_types = ["person", "organization", "concept", "location"]
        
        for _ in range(count):
            entity_type = random.choice(entity_types)
            
            if entity_type == "person":
                entities.append(EntityFactory.create_person_entity())
            elif entity_type == "organization":
                entities.append(EntityFactory.create_organization_entity())
            elif entity_type == "concept":
                entities.append(EntityFactory.create_concept_entity())
            elif entity_type == "location":
                entities.append(EntityFactory.create_location_entity())
        
        return entities


class RelationshipFactory:
    """Factory for generating test relationships"""
    
    @staticmethod
    def create_relationship(
        source_entity: TestEntity,
        target_entity: TestEntity,
        relationship_type: Optional[str] = None
    ) -> TestRelationship:
        """Create a relationship between two entities"""
        
        if not relationship_type:
            # Determine relationship type based on entity types
            if source_entity.entity_type == "person" and target_entity.entity_type == "organization":
                relationship_type = "works_at"
            elif source_entity.entity_type == "person" and target_entity.entity_type == "person":
                relationship_type = random.choice(["knows", "collaborates_with", "manages"])
            elif source_entity.entity_type == "organization" and target_entity.entity_type == "location":
                relationship_type = "located_in"
            elif source_entity.entity_type == "person" and target_entity.entity_type == "concept":
                relationship_type = "expert_in"
            else:
                relationship_type = "related_to"
        
        return TestRelationship(
            uuid=str(uuid.uuid4()),
            source_uuid=source_entity.uuid,
            target_uuid=target_entity.uuid,
            relationship_type=relationship_type,
            weight=random.uniform(0.1, 1.0),
            metadata={
                "created_at": datetime.now().isoformat(),
                "confidence": random.uniform(0.5, 1.0),
                "source": "test_factory"
            }
        )
    
    @staticmethod
    def create_relationship_network(entities: List[TestEntity]) -> List[TestRelationship]:
        """Create a network of relationships between entities"""
        relationships = []
        
        # Ensure we have enough entities
        if len(entities) < 2:
            return relationships
        
        # Create relationships randomly
        for _ in range(min(len(entities) * 2, 50)):  # Limit relationships
            source = random.choice(entities)
            target = random.choice([e for e in entities if e.uuid != source.uuid])
            
            # Avoid duplicate relationships
            existing = any(
                r.source_uuid == source.uuid and r.target_uuid == target.uuid
                for r in relationships
            )
            
            if not existing:
                relationships.append(
                    RelationshipFactory.create_relationship(source, target)
                )
        
        return relationships


class UserFactory:
    """Factory for generating test users"""
    
    @staticmethod
    def create_user(
        username: Optional[str] = None,
        email: Optional[str] = None,
        permissions: Optional[List[str]] = None
    ) -> TestUser:
        """Create a test user"""
        if not username:
            username = fake.user_name()
        
        if not email:
            email = fake.email()
        
        if not permissions:
            permissions = ["read", "write"]
        
        return TestUser(
            user_id=str(uuid.uuid4()),
            username=username,
            email=email,
            api_key=f"test_key_{''.join(random.choices(string.ascii_letters + string.digits, k=32))}",
            permissions=permissions,
            created_at=fake.date_time_between(start_date='-1y', end_date='now')
        )
    
    @staticmethod
    def create_admin_user() -> TestUser:
        """Create an admin test user"""
        return UserFactory.create_user(
            username="test_admin",
            email="admin@test.com",
            permissions=["read", "write", "admin", "delete"]
        )
    
    @staticmethod
    def create_readonly_user() -> TestUser:
        """Create a read-only test user"""
        return UserFactory.create_user(
            username="test_readonly",
            email="readonly@test.com",
            permissions=["read"]
        )


class QueryFactory:
    """Factory for generating test queries"""
    
    SAMPLE_QUERIES = [
        "What are the main concepts discussed in this document?",
        "Who are the key people mentioned?",
        "What organizations are involved?",
        "Summarize the key findings",
        "What relationships exist between the entities?",
        "Find all documents related to artificial intelligence",
        "What are the performance metrics mentioned?",
        "List all the locations referenced",
        "What are the technical specifications?",
        "How does this relate to previous research?"
    ]
    
    @staticmethod
    def create_simple_query() -> str:
        """Create a simple test query"""
        return random.choice(QueryFactory.SAMPLE_QUERIES)
    
    @staticmethod
    def create_complex_query() -> str:
        """Create a complex multi-part query"""
        parts = [
            "Given the information in the documents,",
            random.choice([
                "analyze the relationships between",
                "compare and contrast",
                "identify patterns in",
                "summarize the key points about"
            ]),
            random.choice([
                "the entities and their connections",
                "the main concepts and their applications",
                "the organizations and their roles",
                "the timeline of events"
            ]),
            "and provide",
            random.choice([
                "actionable insights",
                "detailed recommendations", 
                "a comprehensive summary",
                "potential next steps"
            ])
        ]
        return " ".join(parts) + "."
    
    @staticmethod
    def create_query_batch(count: int = 10, complex_ratio: float = 0.3) -> List[str]:
        """Create a batch of test queries"""
        queries = []
        complex_count = int(count * complex_ratio)
        
        for i in range(count):
            if i < complex_count:
                queries.append(QueryFactory.create_complex_query())
            else:
                queries.append(QueryFactory.create_simple_query())
        
        return queries


# Security test data
class SecurityTestData:
    """Test data for security testing"""
    
    SQL_INJECTION_PAYLOADS = [
        "'; DROP TABLE users; --",
        "' OR '1'='1",
        "admin'--",
        "' UNION SELECT * FROM users--",
        "'; INSERT INTO users (username) VALUES ('hacker'); --"
    ]
    
    XSS_PAYLOADS = [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "javascript:alert('XSS')",
        "<svg onload=alert('XSS')>",
        "';alert('XSS');//"
    ]
    
    COMMAND_INJECTION_PAYLOADS = [
        "; ls -la",
        "| cat /etc/passwd",
        "&& rm -rf /",
        "`rm -rf /`",
        "$(cat /etc/passwd)"
    ]
    
    PATH_TRAVERSAL_PAYLOADS = [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\config\\sam",
        "....//....//....//etc/passwd",
        "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd"
    ]
    
    @staticmethod
    def create_malicious_document(payload_type: str = "xss") -> TestDocument:
        """Create a document with malicious content"""
        payloads = {
            "xss": SecurityTestData.XSS_PAYLOADS,
            "sql": SecurityTestData.SQL_INJECTION_PAYLOADS,
            "command": SecurityTestData.COMMAND_INJECTION_PAYLOADS
        }
        
        payload = random.choice(payloads.get(payload_type, SecurityTestData.XSS_PAYLOADS))
        content = f"This document contains malicious content: {payload}"
        
        return DocumentFactory.create_text_document(
            filename=f"malicious_{payload_type}.txt",
            content=content
        )


# Performance test data generators
class PerformanceTestData:
    """Test data for performance testing"""
    
    @staticmethod
    def create_bulk_documents(count: int = 100) -> List[TestDocument]:
        """Create bulk documents for load testing"""
        documents = []
        
        for i in range(count):
            doc_type = random.choice(["text", "pdf", "image", "csv"])
            
            if doc_type == "text":
                documents.append(DocumentFactory.create_text_document())
            elif doc_type == "pdf":
                documents.append(DocumentFactory.create_pdf_document())
            elif doc_type == "image":
                documents.append(DocumentFactory.create_image_document())
            elif doc_type == "csv":
                documents.append(DocumentFactory.create_csv_document())
        
        return documents
    
    @staticmethod
    def create_concurrent_queries(count: int = 50) -> List[str]:
        """Create queries for concurrent testing"""
        return QueryFactory.create_query_batch(count, complex_ratio=0.5)