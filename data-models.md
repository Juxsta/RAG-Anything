# Data Models and Transformation Patterns - RAG-Anything + Graphiti Integration

## Executive Summary

This document defines the data models and transformation patterns for converting multimodal content from RAG-Anything's processing pipeline into Graphiti's episode-based knowledge graph format. The transformations preserve semantic meaning, spatial relationships, and temporal information while enabling rich knowledge graph construction.

## Core Data Models

### Unified Processing Models

#### ProcessedDocument
The primary container for all processed multimodal content, serving as input to both backend implementations.

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum

@dataclass
class ProcessedDocument:
    """Unified document representation post-processing"""
    
    # Document Identity
    document_id: str
    filename: str
    content_type: str
    file_size: int
    processed_at: datetime
    
    # Content by Modality
    text_chunks: List['TextChunk'] = field(default_factory=list)
    images: List['ImageContent'] = field(default_factory=list)  
    tables: List['TableContent'] = field(default_factory=list)
    equations: List['EquationContent'] = field(default_factory=list)
    
    # Processing Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    parser_info: 'ParserInfo' = field(default_factory=lambda: ParserInfo())
    processing_stats: 'ProcessingStats' = field(default_factory=lambda: ProcessingStats())
    
    # Backend-specific processed results
    lightrag_result: Optional['LightRAGResult'] = None
    graphiti_result: Optional['GraphitiResult'] = None
    
    def get_content_by_type(self, content_type: str) -> List[Any]:
        """Get all content of a specific type"""
        content_map = {
            'text': self.text_chunks,
            'image': self.images,
            'table': self.tables,
            'equation': self.equations
        }
        return content_map.get(content_type, [])
    
    def get_temporal_ordering(self) -> List[Any]:
        """Get all content ordered by spatial/temporal position"""
        all_content = []
        for content_list in [self.text_chunks, self.images, self.tables, self.equations]:
            all_content.extend(content_list)
        
        return sorted(all_content, key=lambda x: (
            getattr(x.spatial_context, 'page_number', 0),
            getattr(x.spatial_context, 'position', {}).get('y', 0)
        ))
```

### Content-Specific Models

#### TextChunk
```python
@dataclass
class TextChunk:
    """Text content chunk with context information"""
    
    chunk_id: str
    content: str
    chunk_index: int
    total_chunks: int
    
    # Hierarchical Context
    heading_context: List[str] = field(default_factory=list)
    section_title: Optional[str] = None
    parent_section: Optional[str] = None
    
    # Spatial Information
    spatial_context: Optional['SpatialContext'] = None
    
    # Processing Metadata
    token_count: int = 0
    language: str = "en"
    confidence_score: float = 1.0
    
    # Relationship Information
    related_chunks: List[str] = field(default_factory=list)
    references: List['ContentReference'] = field(default_factory=list)
    
    def to_episode_params(self, document: ProcessedDocument) -> Dict[str, Any]:
        """Convert to Graphiti episode parameters"""
        return {
            'name': f"{document.filename} - {self.section_title or f'Chunk {self.chunk_index}'}",
            'episode_body': self.content,
            'source_description': f"Text content from {document.filename} (page {self.spatial_context.page_number if self.spatial_context else 'unknown'})",
            'reference_time': document.processed_at,
            'source': EpisodeType.document,
            'content_type': 'text',
            'spatial_context': self.spatial_context,
            'hierarchical_context': {
                'headings': self.heading_context,
                'section': self.section_title,
                'parent': self.parent_section
            }
        }
```

#### ImageContent
```python
@dataclass  
class ImageContent:
    """Image content with vision model analysis"""
    
    image_id: str
    image_path: str
    image_format: str
    image_size: tuple[int, int]  # (width, height)
    
    # Vision Analysis
    description: str
    detailed_analysis: Optional[str] = None
    detected_objects: List['DetectedObject'] = field(default_factory=list)
    extracted_text: Optional[str] = None  # OCR results
    
    # Spatial Context
    spatial_context: Optional['SpatialContext'] = None
    
    # Caption and Context
    caption: Optional[str] = None
    surrounding_text: Optional[str] = None
    alt_text: Optional[str] = None
    
    # Processing Metadata
    vision_model_used: str = ""
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    processing_time: float = 0.0
    
    def to_episode_params(self, document: ProcessedDocument) -> Dict[str, Any]:
        """Convert to Graphiti episode parameters"""
        # Combine description with extracted text and caption
        content_parts = [self.description]
        if self.extracted_text:
            content_parts.append(f"Extracted text: {self.extracted_text}")
        if self.caption:
            content_parts.append(f"Caption: {self.caption}")
        
        episode_content = "\n\n".join(content_parts)
        
        return {
            'name': f"{document.filename} - Image {self.image_id}",
            'episode_body': episode_content,
            'source_description': f"Image analysis from {document.filename} using {self.vision_model_used}",
            'reference_time': document.processed_at,
            'source': EpisodeType.media,
            'content_type': 'image',
            'spatial_context': self.spatial_context,
            'image_metadata': {
                'format': self.image_format,
                'size': self.image_size,
                'path': self.image_path,
                'objects_detected': len(self.detected_objects),
                'has_text': bool(self.extracted_text)
            }
        }
```

#### TableContent
```python
@dataclass
class TableContent:
    """Table content with structured data"""
    
    table_id: str
    headers: List[str]
    rows: List[List[str]]
    table_type: str  # 'data', 'summary', 'comparison', etc.
    
    # Structure Analysis
    column_types: Dict[str, str] = field(default_factory=dict)  # column_name -> data_type
    statistical_summary: Optional[Dict[str, Any]] = None
    key_relationships: List['TableRelationship'] = field(default_factory=list)
    
    # Context Information
    title: Optional[str] = None
    caption: Optional[str] = None
    surrounding_text: Optional[str] = None
    spatial_context: Optional['SpatialContext'] = None
    
    # Processing Metadata
    extraction_confidence: float = 1.0
    data_quality_score: float = 1.0
    
    def to_structured_text(self) -> str:
        """Convert table to structured text representation"""
        lines = []
        if self.title:
            lines.append(f"Table: {self.title}")
        
        # Add headers
        if self.headers:
            lines.append(" | ".join(self.headers))
            lines.append("-" * len(" | ".join(self.headers)))
        
        # Add rows
        for row in self.rows:
            lines.append(" | ".join(str(cell) for cell in row))
        
        if self.caption:
            lines.append(f"\nCaption: {self.caption}")
            
        return "\n".join(lines)
    
    def to_episode_params(self, document: ProcessedDocument) -> Dict[str, Any]:
        """Convert to Graphiti episode parameters"""
        content_parts = []
        
        # Add table structure
        content_parts.append(self.to_structured_text())
        
        # Add analysis
        if self.statistical_summary:
            summary_text = self._format_statistical_summary()
            content_parts.append(f"\nStatistical Analysis:\n{summary_text}")
        
        # Add relationships
        if self.key_relationships:
            rel_text = self._format_relationships()
            content_parts.append(f"\nKey Relationships:\n{rel_text}")
        
        return {
            'name': f"{document.filename} - Table: {self.title or self.table_id}",
            'episode_body': "\n\n".join(content_parts),
            'source_description': f"Table data from {document.filename}",
            'reference_time': document.processed_at,
            'source': EpisodeType.document,
            'content_type': 'table',
            'spatial_context': self.spatial_context,
            'table_metadata': {
                'headers': self.headers,
                'row_count': len(self.rows),
                'column_count': len(self.headers),
                'data_types': self.column_types,
                'table_type': self.table_type
            }
        }
    
    def _format_statistical_summary(self) -> str:
        """Format statistical summary for episode content"""
        if not self.statistical_summary:
            return ""
        
        lines = []
        for column, stats in self.statistical_summary.items():
            lines.append(f"- {column}: {stats}")
        return "\n".join(lines)
    
    def _format_relationships(self) -> str:
        """Format table relationships for episode content"""
        lines = []
        for rel in self.key_relationships:
            lines.append(f"- {rel.description}")
        return "\n".join(lines)
```

#### EquationContent  
```python
@dataclass
class EquationContent:
    """Mathematical equation content"""
    
    equation_id: str
    latex_notation: str
    natural_language_description: str
    
    # Mathematical Analysis
    variables: List['MathVariable'] = field(default_factory=list)
    constants: List['MathConstant'] = field(default_factory=list)
    equation_type: str = ""  # 'linear', 'quadratic', 'differential', etc.
    domain: Optional[str] = None  # 'algebra', 'calculus', 'statistics', etc.
    
    # Context Information
    surrounding_text: Optional[str] = None
    equation_number: Optional[str] = None
    spatial_context: Optional['SpatialContext'] = None
    
    # Relationships
    related_equations: List[str] = field(default_factory=list)
    referenced_by: List['ContentReference'] = field(default_factory=list)
    
    def to_episode_params(self, document: ProcessedDocument) -> Dict[str, Any]:
        """Convert to Graphiti episode parameters"""
        content_parts = []
        
        # Add natural language description
        content_parts.append(self.natural_language_description)
        
        # Add LaTeX notation
        content_parts.append(f"Mathematical notation: {self.latex_notation}")
        
        # Add variable definitions
        if self.variables:
            var_text = self._format_variables()
            content_parts.append(f"Variables:\n{var_text}")
        
        # Add constants
        if self.constants:
            const_text = self._format_constants()
            content_parts.append(f"Constants:\n{const_text}")
        
        # Add context
        if self.surrounding_text:
            content_parts.append(f"Context: {self.surrounding_text}")
        
        return {
            'name': f"{document.filename} - Equation {self.equation_number or self.equation_id}",
            'episode_body': "\n\n".join(content_parts),
            'source_description': f"Mathematical equation from {document.filename}",
            'reference_time': document.processed_at,
            'source': EpisodeType.document,
            'content_type': 'equation',
            'spatial_context': self.spatial_context,
            'math_metadata': {
                'latex': self.latex_notation,
                'equation_type': self.equation_type,
                'domain': self.domain,
                'variable_count': len(self.variables),
                'constant_count': len(self.constants)
            }
        }
    
    def _format_variables(self) -> str:
        """Format variables for episode content"""
        lines = []
        for var in self.variables:
            lines.append(f"- {var.symbol}: {var.description}")
        return "\n".join(lines)
    
    def _format_constants(self) -> str:
        """Format constants for episode content"""
        lines = []
        for const in self.constants:
            lines.append(f"- {const.symbol} = {const.value}: {const.description}")
        return "\n".join(lines)
```

### Supporting Models

#### SpatialContext
```python
@dataclass
class SpatialContext:
    """Spatial positioning information for content"""
    
    page_number: int
    position: Dict[str, float]  # {'x': float, 'y': float, 'width': float, 'height': float}
    z_index: Optional[int] = None  # For layered content
    
    # Relative positioning
    relative_to: Optional[str] = None  # ID of reference content
    relationship: Optional[str] = None  # 'above', 'below', 'left', 'right', 'inside'
    
    def distance_to(self, other: 'SpatialContext') -> float:
        """Calculate distance to another spatial context"""
        if self.page_number != other.page_number:
            return float('inf')  # Different pages are infinitely far
        
        dx = self.position['x'] - other.position['x']
        dy = self.position['y'] - other.position['y']
        return (dx**2 + dy**2)**0.5
    
    def is_nearby(self, other: 'SpatialContext', threshold: float = 50.0) -> bool:
        """Check if another context is spatially nearby"""
        return self.distance_to(other) < threshold
```

#### ContentReference
```python
@dataclass
class ContentReference:
    """Reference between different pieces of content"""
    
    source_id: str
    target_id: str
    reference_type: str  # 'mentions', 'describes', 'explains', 'supports', 'contradicts'
    context: Optional[str] = None
    confidence: float = 1.0
```

#### EpisodeType (Enum)
```python
from enum import Enum

class EpisodeType(Enum):
    """Graphiti episode source types"""
    message = "message"
    document = "document" 
    media = "media"
    system = "system"
```

### Backend-Specific Result Models

#### LightRAGResult
```python
@dataclass
class LightRAGResult:
    """Results from LightRAG processing"""
    
    status: str  # 'success', 'partial', 'failed'
    chunks_processed: int
    total_tokens: int
    processing_time: float
    
    # Storage information
    storage_paths: Dict[str, str] = field(default_factory=dict)
    
    # Error information
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
```

#### GraphitiResult
```python
@dataclass
class GraphitiResult:
    """Results from Graphiti processing"""
    
    status: str  # 'success', 'partial', 'failed'
    episodes_created: int
    entities_extracted: int
    relationships_created: int
    processing_time: float
    
    # Episode information
    episode_uuids: List[str] = field(default_factory=list)
    
    # Knowledge graph statistics
    graph_stats: Optional['GraphStats'] = None
    
    # Community information (if built)
    communities_updated: int = 0
    
    # Error information
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

@dataclass
class GraphStats:
    """Knowledge graph statistics"""
    
    total_entities: int
    total_relationships: int
    total_communities: int
    avg_relationships_per_entity: float
    graph_density: float
```

## Transformation Patterns

### Content-to-Episode Conversion Strategy

#### 1. Text Content Transformation
```python
class TextToEpisodeConverter:
    """Converts text chunks to Graphiti episodes"""
    
    def convert(self, text_chunk: TextChunk, document: ProcessedDocument) -> Dict[str, Any]:
        """Convert text chunk to episode parameters"""
        
        # Generate episode name with hierarchical context
        name_parts = [document.filename]
        if text_chunk.heading_context:
            name_parts.extend(text_chunk.heading_context[:2])  # Max 2 levels
        elif text_chunk.section_title:
            name_parts.append(text_chunk.section_title)
        else:
            name_parts.append(f"Section {text_chunk.chunk_index}")
        
        episode_name = " - ".join(name_parts)
        
        # Enrich content with context
        enriched_content = self._enrich_text_content(text_chunk, document)
        
        return {
            'name': episode_name[:200],  # Limit episode name length
            'episode_body': enriched_content,
            'source_description': self._generate_source_description(text_chunk, document),
            'reference_time': self._determine_reference_time(text_chunk, document),
            'source': EpisodeType.document,
            'group_id': self._generate_group_id(document),
            'metadata': {
                'content_type': 'text',
                'chunk_index': text_chunk.chunk_index,
                'spatial_context': text_chunk.spatial_context.__dict__ if text_chunk.spatial_context else None,
                'token_count': text_chunk.token_count,
                'hierarchical_context': {
                    'headings': text_chunk.heading_context,
                    'section': text_chunk.section_title
                }
            }
        }
    
    def _enrich_text_content(self, chunk: TextChunk, document: ProcessedDocument) -> str:
        """Enrich text content with context and metadata"""
        parts = []
        
        # Add hierarchical context
        if chunk.heading_context:
            context_chain = " > ".join(chunk.heading_context)
            parts.append(f"Document section: {context_chain}\n")
        
        # Add main content
        parts.append(chunk.content)
        
        # Add spatial context
        if chunk.spatial_context:
            parts.append(f"\n[Location: Page {chunk.spatial_context.page_number}]")
        
        # Add references to nearby content
        nearby_refs = self._get_nearby_content_references(chunk, document)
        if nearby_refs:
            parts.append(f"\nRelated content: {nearby_refs}")
        
        return "\n".join(parts)
    
    def _get_nearby_content_references(self, chunk: TextChunk, document: ProcessedDocument) -> str:
        """Get references to nearby images, tables, or equations"""
        if not chunk.spatial_context:
            return ""
        
        references = []
        
        # Check for nearby images
        for img in document.images:
            if (img.spatial_context and 
                chunk.spatial_context.is_nearby(img.spatial_context)):
                references.append(f"Image {img.image_id}")
        
        # Check for nearby tables
        for table in document.tables:
            if (table.spatial_context and 
                chunk.spatial_context.is_nearby(table.spatial_context)):
                references.append(f"Table '{table.title or table.table_id}'")
        
        # Check for nearby equations
        for eq in document.equations:
            if (eq.spatial_context and 
                chunk.spatial_context.is_nearby(eq.spatial_context)):
                references.append(f"Equation {eq.equation_number or eq.equation_id}")
        
        return ", ".join(references) if references else ""
```

#### 2. Multimodal Content Cross-Referencing
```python
class CrossModalReferenceBuilder:
    """Builds relationships between different content types"""
    
    def build_references(self, document: ProcessedDocument) -> List[ContentReference]:
        """Build cross-modal references for the document"""
        references = []
        
        # Text-Image references
        references.extend(self._build_text_image_refs(document))
        
        # Text-Table references  
        references.extend(self._build_text_table_refs(document))
        
        # Text-Equation references
        references.extend(self._build_text_equation_refs(document))
        
        # Image-Table references
        references.extend(self._build_image_table_refs(document))
        
        return references
    
    def _build_text_image_refs(self, document: ProcessedDocument) -> List[ContentReference]:
        """Build references between text and images"""
        references = []
        
        for text_chunk in document.text_chunks:
            for image in document.images:
                # Spatial proximity
                if (text_chunk.spatial_context and image.spatial_context and
                    text_chunk.spatial_context.is_nearby(image.spatial_context)):
                    
                    ref_type = self._determine_text_image_relationship(text_chunk, image)
                    references.append(ContentReference(
                        source_id=text_chunk.chunk_id,
                        target_id=image.image_id,
                        reference_type=ref_type,
                        context=f"Spatially proximate on page {text_chunk.spatial_context.page_number}",
                        confidence=0.8
                    ))
                
                # Semantic references
                semantic_ref = self._check_semantic_text_image_ref(text_chunk, image)
                if semantic_ref:
                    references.append(semantic_ref)
        
        return references
    
    def _determine_text_image_relationship(self, text: TextChunk, image: ImageContent) -> str:
        """Determine the type of relationship between text and image"""
        text_lower = text.content.lower()
        
        # Check for explicit references
        if any(ref in text_lower for ref in ['figure', 'image', 'photo', 'diagram']):
            return 'describes'
        
        # Check if image has caption that matches text
        if image.caption and self._text_similarity(text.content, image.caption) > 0.7:
            return 'explains'
        
        # Default spatial relationship
        return 'nearby'
    
    def _check_semantic_text_image_ref(self, text: TextChunk, image: ImageContent) -> Optional[ContentReference]:
        """Check for semantic relationships between text and image content"""
        # Simple keyword matching - could be enhanced with embedding similarity
        text_words = set(text.content.lower().split())
        image_words = set(image.description.lower().split())
        
        # Calculate word overlap
        overlap = len(text_words.intersection(image_words))
        total_words = len(text_words.union(image_words))
        
        if total_words > 0 and overlap / total_words > 0.3:  # 30% word overlap threshold
            return ContentReference(
                source_id=text.chunk_id,
                target_id=image.image_id,
                reference_type='semantically_related',
                context=f"Semantic overlap: {overlap}/{total_words} words",
                confidence=overlap / total_words
            )
        
        return None
```

#### 3. Temporal Information Management
```python
class TemporalInformationManager:
    """Manages temporal information for episodes"""
    
    def determine_reference_time(self, content: Any, document: ProcessedDocument) -> datetime:
        """Determine appropriate reference time for content"""
        
        # Priority order for timestamp selection:
        # 1. Content-specific timestamp (if available)
        # 2. Document creation time (from metadata)
        # 3. Document modification time (from filesystem)
        # 4. Processing time (fallback)
        
        # Check for document metadata timestamps
        if document.metadata.get('creation_date'):
            try:
                return datetime.fromisoformat(document.metadata['creation_date'])
            except (ValueError, TypeError):
                pass
        
        if document.metadata.get('modification_date'):
            try:
                return datetime.fromisoformat(document.metadata['modification_date'])
            except (ValueError, TypeError):
                pass
        
        # Fallback to processing time
        return document.processed_at
    
    def generate_temporal_sequences(self, document: ProcessedDocument) -> List[Dict[str, Any]]:
        """Generate temporal sequences for episode ordering"""
        
        # Get all content ordered by spatial position
        ordered_content = document.get_temporal_ordering()
        
        sequences = []
        for i, content in enumerate(ordered_content):
            # Create artificial time progression within document
            base_time = self.determine_reference_time(content, document)
            offset_seconds = i * 10  # 10-second intervals between content pieces
            
            sequence_time = base_time + timedelta(seconds=offset_seconds)
            
            sequences.append({
                'content_id': getattr(content, 'chunk_id', getattr(content, 'image_id', getattr(content, 'table_id', content.equation_id))),
                'reference_time': sequence_time,
                'sequence_index': i,
                'content_type': type(content).__name__
            })
        
        return sequences
```

### Episode Relationship Mapping

#### Relationship Types for Multimodal Content
```python
class EpisodeRelationshipMapper:
    """Maps relationships between episodes based on content relationships"""
    
    RELATIONSHIP_TYPES = {
        'spatial_proximity': 'Content appears near each other in the document',
        'semantic_similarity': 'Content has similar semantic meaning',
        'explanatory': 'One piece of content explains another',
        'supportive': 'One piece of content supports claims in another',
        'hierarchical': 'Content has parent-child relationship (sections/subsections)',
        'sequential': 'Content follows logical sequence in document',
        'cross_modal': 'Different content types referring to same concept'
    }
    
    def map_relationships(self, references: List[ContentReference], 
                         episodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Map content references to episode relationships"""
        
        episode_map = {ep['metadata']['content_id']: ep for ep in episodes}
        relationships = []
        
        for ref in references:
            source_episode = episode_map.get(ref.source_id)
            target_episode = episode_map.get(ref.target_id)
            
            if source_episode and target_episode:
                relationships.append({
                    'source_episode_name': source_episode['name'],
                    'target_episode_name': target_episode['name'],
                    'relationship_type': ref.reference_type,
                    'context': ref.context,
                    'confidence': ref.confidence,
                    'bidirectional': self._is_bidirectional_relationship(ref.reference_type)
                })
        
        return relationships
    
    def _is_bidirectional_relationship(self, relationship_type: str) -> bool:
        """Determine if relationship type is bidirectional"""
        bidirectional_types = {'spatial_proximity', 'semantic_similarity', 'cross_modal'}
        return relationship_type in bidirectional_types
```

## Implementation Examples

### Complete Document Processing Pipeline
```python
class MultimodalEpisodeConverter:
    """Main converter class orchestrating all transformations"""
    
    def __init__(self):
        self.text_converter = TextToEpisodeConverter()
        self.reference_builder = CrossModalReferenceBuilder()
        self.temporal_manager = TemporalInformationManager()
        self.relationship_mapper = EpisodeRelationshipMapper()
    
    async def convert_document(self, document: ProcessedDocument) -> List[Dict[str, Any]]:
        """Convert entire document to Graphiti episodes"""
        episodes = []
        
        # Convert all content types to episodes
        for text_chunk in document.text_chunks:
            episode = text_chunk.to_episode_params(document)
            episode['metadata']['content_id'] = text_chunk.chunk_id
            episodes.append(episode)
        
        for image in document.images:
            episode = image.to_episode_params(document)
            episode['metadata']['content_id'] = image.image_id
            episodes.append(episode)
        
        for table in document.tables:
            episode = table.to_episode_params(document)
            episode['metadata']['content_id'] = table.table_id
            episodes.append(episode)
        
        for equation in document.equations:
            episode = equation.to_episode_params(document)
            episode['metadata']['content_id'] = equation.equation_id
            episodes.append(episode)
        
        # Build cross-modal references
        references = self.reference_builder.build_references(document)
        
        # Apply temporal sequencing
        temporal_sequences = self.temporal_manager.generate_temporal_sequences(document)
        self._apply_temporal_sequences(episodes, temporal_sequences)
        
        # Map relationships
        relationships = self.relationship_mapper.map_relationships(references, episodes)
        
        # Enrich episodes with relationship metadata
        self._enrich_episodes_with_relationships(episodes, relationships)
        
        return episodes
    
    def _apply_temporal_sequences(self, episodes: List[Dict[str, Any]], 
                                sequences: List[Dict[str, Any]]) -> None:
        """Apply temporal sequencing to episodes"""
        sequence_map = {seq['content_id']: seq for seq in sequences}
        
        for episode in episodes:
            content_id = episode['metadata']['content_id']
            if content_id in sequence_map:
                episode['reference_time'] = sequence_map[content_id]['reference_time']
                episode['metadata']['sequence_index'] = sequence_map[content_id]['sequence_index']
    
    def _enrich_episodes_with_relationships(self, episodes: List[Dict[str, Any]], 
                                          relationships: List[Dict[str, Any]]) -> None:
        """Enrich episodes with relationship information"""
        
        # Create lookup maps
        episode_by_name = {ep['name']: ep for ep in episodes}
        
        for relationship in relationships:
            source_name = relationship['source_episode_name']
            target_name = relationship['target_episode_name']
            
            # Add relationship info to source episode
            if source_name in episode_by_name:
                if 'relationships' not in episode_by_name[source_name]['metadata']:
                    episode_by_name[source_name]['metadata']['relationships'] = []
                
                episode_by_name[source_name]['metadata']['relationships'].append({
                    'target': target_name,
                    'type': relationship['relationship_type'],
                    'context': relationship['context'],
                    'confidence': relationship['confidence']
                })
```

### Usage Example
```python
async def process_document_for_graphiti():
    """Example of complete document processing for Graphiti backend"""
    
    # 1. Process document with existing RAG-Anything pipeline
    document = await process_document_with_raganything("example.pdf")
    
    # 2. Convert to episodes
    converter = MultimodalEpisodeConverter()
    episodes = await converter.convert_document(document)
    
    # 3. Insert episodes into Graphiti
    graphiti = get_graphiti_instance()
    
    results = []
    for episode_params in episodes:
        result = await graphiti.add_episode(**episode_params)
        results.append(result)
    
    # 4. Build communities if desired
    if should_build_communities():
        communities = await graphiti.build_communities()
    
    return {
        'episodes_created': len(results),
        'entities_extracted': sum(len(r.nodes) for r in results),
        'relationships_created': sum(len(r.edges) for r in results)
    }
```

This comprehensive data model and transformation system ensures that all multimodal content from RAG-Anything is properly converted into Graphiti's episode-based format while preserving semantic relationships, spatial context, and temporal information. The modular design allows for easy extension and customization of the conversion process.