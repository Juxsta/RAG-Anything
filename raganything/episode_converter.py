"""
Episode Converter for Graphiti Integration.

This module converts multimodal content from RAG-Anything's processing pipeline
into structured episodes suitable for Graphiti's episodic knowledge graph.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum

from lightrag.utils import logger

try:
    from graphiti_core.nodes import EpisodeType
    GRAPHITI_AVAILABLE = True
except ImportError:
    GRAPHITI_AVAILABLE = False
    # Define fallback enum
    class EpisodeType(Enum):
        message = "message"
        json = "json"
        text = "text"


class ContentType(Enum):
    """Types of multimodal content"""
    TEXT = "text"
    IMAGE = "image"
    TABLE = "table" 
    EQUATION = "equation"
    CONTEXT = "context"
    MIXED = "mixed"
    CODE = "code"
    DIAGRAM = "diagram"
    CHART = "chart"
    METADATA = "metadata"


@dataclass
class EpisodeContent:
    """Structured episode content for Graphiti"""
    name: str
    episode_body: str
    source_description: str
    reference_time: datetime
    episode_type: EpisodeType = EpisodeType.message
    group_id: str = "default"
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Additional metadata
    content_types: List[ContentType] = field(default_factory=list)
    original_metadata: Dict[str, Any] = field(default_factory=dict)
    semantic_tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for Graphiti API"""
        return {
            "name": self.name,
            "episode_body": self.episode_body,
            "source_description": self.source_description,
            "reference_time": self.reference_time,
            "source": self.episode_type,
            "group_id": self.group_id,
            "uuid": self.uuid,
        }


class EpisodeConverter:
    """
    Converts multimodal content into structured episodes for Graphiti.
    
    This class handles the transformation of parsed documents and multimodal
    content from RAG-Anything's processing pipeline into episodes that can
    be efficiently processed by Graphiti's episodic knowledge graph.
    """
    
    def __init__(self, default_group_id: str = "default", 
                 preserve_document_structure: bool = True):
        """
        Initialize the episode converter.
        
        Args:
            default_group_id: Default group ID for episodes
            preserve_document_structure: Whether to maintain document hierarchy
        """
        self.default_group_id = default_group_id
        self.preserve_document_structure = preserve_document_structure
        self.logger = logger
        
    def convert_document(
        self,
        document_content: Union[Dict[str, Any], List[Dict[str, Any]]],
        document_metadata: Optional[Dict[str, Any]] = None
    ) -> List[EpisodeContent]:
        """
        Convert a complete document into a series of episodes.
        
        Args:
            document_content: Parsed document content from RAG-Anything
            document_metadata: Document-level metadata
            
        Returns:
            List of EpisodeContent objects ready for Graphiti
        """
        episodes = []
        doc_metadata = document_metadata or {}
        
        try:
            if isinstance(document_content, dict):
                # Single content item
                episode = self._convert_content_item(document_content, doc_metadata)
                if episode:
                    episodes.append(episode)
            elif isinstance(document_content, list):
                # Multiple content items (typical for parsed documents)
                for i, content_item in enumerate(document_content):
                    episode = self._convert_content_item(
                        content_item, 
                        doc_metadata, 
                        item_index=i
                    )
                    if episode:
                        episodes.append(episode)
            
            self.logger.info(f"Converted document to {len(episodes)} episodes")
            return episodes
            
        except Exception as e:
            self.logger.error(f"Error converting document to episodes: {e}")
            return []
    
    def _convert_content_item(
        self,
        content: Dict[str, Any],
        metadata: Dict[str, Any],
        item_index: Optional[int] = None
    ) -> Optional[EpisodeContent]:
        """Convert a single content item into an episode"""
        try:
            # Determine content type and create appropriate episode
            content_types = self._identify_content_types(content)
            
            # Generate episode name
            name = self._generate_episode_name(content, metadata, item_index)
            
            # Create episode body
            episode_body = self._create_episode_body(content, content_types)
            
            # Determine episode type based on content
            episode_type = self._determine_episode_type(content_types)
            
            # Extract source description
            source_description = self._create_source_description(content, metadata)
            
            # Get reference time
            reference_time = self._extract_reference_time(content, metadata)
            
            # Get group ID
            group_id = metadata.get('group_id', self.default_group_id)
            
            # Generate semantic tags
            semantic_tags = self._generate_semantic_tags(content, content_types)
            
            return EpisodeContent(
                name=name,
                episode_body=episode_body,
                source_description=source_description,
                reference_time=reference_time,
                episode_type=episode_type,
                group_id=group_id,
                content_types=content_types,
                original_metadata=metadata,
                semantic_tags=semantic_tags
            )
            
        except Exception as e:
            self.logger.error(f"Error converting content item to episode: {e}")
            return None
    
    def _identify_content_types(self, content: Dict[str, Any]) -> List[ContentType]:
        """Identify the types of content present with enhanced detection"""
        content_types = []
        
        # Check for different content types with expanded detection
        if any(key in content for key in ['text', 'content', 'body', 'raw_text']):
            content_types.append(ContentType.TEXT)
        
        if any(key in content for key in ['image', 'image_path', 'image_caption', 'image_description', 'image_data', 'figure']):
            content_types.append(ContentType.IMAGE)
        
        if any(key in content for key in ['table', 'table_content', 'table_data', 'tabular_data', 'csv_data']):
            content_types.append(ContentType.TABLE)
        
        if any(key in content for key in ['equation', 'formula', 'math', 'latex', 'mathematical_expression']):
            content_types.append(ContentType.EQUATION)
        
        if any(key in content for key in ['code', 'source_code', 'programming_code', 'script']):
            content_types.append(ContentType.CODE)
        
        if any(key in content for key in ['diagram', 'flowchart', 'schema', 'architecture']):
            content_types.append(ContentType.DIAGRAM)
        
        if any(key in content for key in ['chart', 'graph', 'plot', 'visualization']):
            content_types.append(ContentType.CHART)
        
        if 'context' in content:
            content_types.append(ContentType.CONTEXT)
        
        # Check for metadata indicators
        if any(key in content for key in ['metadata', 'page', 'page_number', 'section', 'title', 'author']):
            content_types.append(ContentType.METADATA)
        
        # Enhanced content analysis based on text patterns
        text_content = self._extract_text_for_analysis(content)
        if text_content:
            content_types.extend(self._analyze_text_patterns(text_content))
        
        # If multiple types, mark as mixed
        if len(content_types) > 1:
            content_types.append(ContentType.MIXED)
        
        return content_types if content_types else [ContentType.TEXT]
    
    def _extract_text_for_analysis(self, content: Dict[str, Any]) -> str:
        """Extract text content for pattern analysis"""
        text_sources = ['text', 'content', 'body', 'raw_text', 'description']
        for key in text_sources:
            if key in content and content[key]:
                return str(content[key])
        return ""
    
    def _analyze_text_patterns(self, text: str) -> List[ContentType]:
        """Analyze text patterns to identify additional content types"""
        additional_types = []
        text_lower = text.lower()
        
        # Code pattern detection
        code_indicators = ['def ', 'function ', 'class ', 'import ', 'from ', '#!/', 'SELECT ', 'INSERT ', 'UPDATE ']
        if any(indicator in text for indicator in code_indicators):
            additional_types.append(ContentType.CODE)
        
        # Mathematical content detection
        math_indicators = ['∑', '∫', '∂', '≈', '≤', '≥', '∞', '±', 'equation', 'theorem', 'proof']
        if any(indicator in text_lower for indicator in math_indicators):
            additional_types.append(ContentType.EQUATION)
        
        # Diagram/Chart references
        visual_indicators = ['figure', 'chart', 'graph', 'diagram', 'plot', 'visualization']
        if any(f'see {indicator}' in text_lower or f'in {indicator}' in text_lower for indicator in visual_indicators):
            additional_types.append(ContentType.DIAGRAM)
        
        return additional_types
    
    def _generate_episode_name(
        self,
        content: Dict[str, Any],
        metadata: Dict[str, Any],
        item_index: Optional[int] = None
    ) -> str:
        """Generate a descriptive name for the episode"""
        # Try to use explicit title
        if 'title' in content:
            return content['title']
        
        if 'name' in content:
            return content['name']
        
        # Use document title with index
        doc_title = metadata.get('title', metadata.get('filename', 'Document'))
        
        if item_index is not None:
            return f"{doc_title} - Section {item_index + 1}"
        
        # Generate based on content type
        content_types = self._identify_content_types(content)
        if ContentType.IMAGE in content_types:
            return f"{doc_title} - Image Content"
        elif ContentType.TABLE in content_types:
            return f"{doc_title} - Table Content"
        elif ContentType.EQUATION in content_types:
            return f"{doc_title} - Mathematical Content"
        else:
            return f"{doc_title} - Text Content"
    
    def _create_episode_body(
        self,
        content: Dict[str, Any],
        content_types: List[ContentType]
    ) -> str:
        """Create the main episode body content with enhanced multimodal support"""
        sections = []
        
        # Add main text content
        for text_key in ['text', 'content', 'body', 'raw_text']:
            if text_key in content and content[text_key]:
                sections.append(str(content[text_key]))
                break
        
        # Add contextual information
        if 'context' in content and content['context']:
            sections.append(f"Context: {content['context']}")
        
        # Add image descriptions with enhanced handling
        image_keys = ['image_caption', 'image_description', 'figure', 'image_data']
        for image_key in image_keys:
            if image_key in content and content[image_key]:
                if image_key == 'image_data':
                    sections.append(f"Image: [Image data present - {len(str(content[image_key]))} characters]")
                else:
                    sections.append(f"Visual Content: {content[image_key]}")
                break
        
        # Add table content with multiple format support
        table_keys = ['table_content', 'table_data', 'tabular_data', 'csv_data']
        for table_key in table_keys:
            if table_key in content and content[table_key]:
                sections.append(f"Tabular Data:\n{content[table_key]}")
                break
        
        # Add mathematical content
        math_keys = ['equation', 'formula', 'math', 'latex', 'mathematical_expression']
        for math_key in math_keys:
            if math_key in content and content[math_key]:
                sections.append(f"Mathematical Expression: {content[math_key]}")
                break
        
        # Add code content
        code_keys = ['code', 'source_code', 'programming_code', 'script']
        for code_key in code_keys:
            if code_key in content and content[code_key]:
                sections.append(f"Code:\n```\n{content[code_key]}\n```")
                break
        
        # Add diagram/chart content
        visual_keys = ['diagram', 'flowchart', 'schema', 'architecture', 'chart', 'graph', 'plot', 'visualization']
        for visual_key in visual_keys:
            if visual_key in content and content[visual_key]:
                sections.append(f"Visual Element ({visual_key.replace('_', ' ').title()}): {content[visual_key]}")
                break
        
        # Add metadata in structured format
        metadata_keys = ['page', 'page_number', 'section', 'author', 'date', 'source']
        metadata_items = []
        for meta_key in metadata_keys:
            if meta_key in content and content[meta_key]:
                metadata_items.append(f"{meta_key.replace('_', ' ').title()}: {content[meta_key]}")
        
        if metadata_items:
            sections.append(f"Document Metadata:\n" + "\n".join(metadata_items))
        
        # Add any additional structured content (excluding processed keys)
        processed_keys = {
            'text', 'content', 'body', 'raw_text', 'context', 
            'image_caption', 'image_description', 'figure', 'image_data',
            'table_content', 'table_data', 'tabular_data', 'csv_data',
            'equation', 'formula', 'math', 'latex', 'mathematical_expression',
            'code', 'source_code', 'programming_code', 'script',
            'diagram', 'flowchart', 'schema', 'architecture', 'chart', 'graph', 'plot', 'visualization',
            'page', 'page_number', 'section', 'author', 'date', 'source',
            'title', 'name', 'timestamp', 'uuid', 'metadata'
        }
        
        additional_content = []
        for key, value in content.items():
            if key not in processed_keys and value:
                formatted_key = key.replace('_', ' ').title()
                if isinstance(value, (dict, list)):
                    additional_content.append(f"{formatted_key}: {str(value)[:200]}...")
                else:
                    additional_content.append(f"{formatted_key}: {value}")
        
        if additional_content:
            sections.append("Additional Content:\n" + "\n".join(additional_content))
        
        return "\n\n".join(sections)
    
    def _determine_episode_type(self, content_types: List[ContentType]) -> EpisodeType:
        """Determine the appropriate Graphiti episode type"""
        # Rules for episode type determination
        if ContentType.IMAGE in content_types:
            return EpisodeType.text  # Visual content as text description
        elif ContentType.TABLE in content_types:
            return EpisodeType.text  # Data content as text
        elif ContentType.EQUATION in content_types:
            return EpisodeType.text  # Mathematical content as text
        elif ContentType.MIXED in content_types:
            return EpisodeType.text  # Complex mixed content as text
        else:
            return EpisodeType.message  # Default to message for text content
    
    def _create_source_description(
        self,
        content: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> str:
        """Create a description of the content source"""
        sources = []
        
        # Document source
        if 'filename' in metadata:
            sources.append(f"Document: {metadata['filename']}")
        elif 'title' in metadata:
            sources.append(f"Document: {metadata['title']}")
        
        # Page information
        if 'page' in content:
            sources.append(f"Page {content['page']}")
        elif 'page_number' in metadata:
            sources.append(f"Page {metadata['page_number']}")
        
        # Content type information
        content_types = self._identify_content_types(content)
        if ContentType.MIXED in content_types:
            sources.append("Multimodal content")
        elif ContentType.IMAGE in content_types:
            sources.append("Visual content")
        elif ContentType.TABLE in content_types:
            sources.append("Tabular data")
        elif ContentType.EQUATION in content_types:
            sources.append("Mathematical content")
        
        # Parser information
        if 'parser' in metadata:
            sources.append(f"Parsed with {metadata['parser']}")
        
        return " - ".join(sources) if sources else "Unknown source"
    
    def _extract_reference_time(
        self,
        content: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> datetime:
        """Extract or generate reference time for the episode"""
        # Try content timestamp first
        if 'timestamp' in content:
            if isinstance(content['timestamp'], datetime):
                return content['timestamp']
            elif isinstance(content['timestamp'], str):
                try:
                    return datetime.fromisoformat(content['timestamp'])
                except ValueError:
                    pass
        
        # Try metadata timestamp
        if 'timestamp' in metadata:
            if isinstance(metadata['timestamp'], datetime):
                return metadata['timestamp']
            elif isinstance(metadata['timestamp'], str):
                try:
                    return datetime.fromisoformat(metadata['timestamp'])
                except ValueError:
                    pass
        
        # Default to current time
        return datetime.now()
    
    def _generate_semantic_tags(
        self,
        content: Dict[str, Any],
        content_types: List[ContentType]
    ) -> List[str]:
        """Generate semantic tags for better categorization"""
        tags = []
        
        # Add content type tags
        for content_type in content_types:
            tags.append(content_type.value)
        
        # Add domain-specific tags based on content analysis
        text_content = ""
        for text_key in ['text', 'content', 'body']:
            if text_key in content and content[text_key]:
                text_content = str(content[text_key]).lower()
                break
        
        # Simple keyword-based tagging (can be enhanced with NLP)
        if any(word in text_content for word in ['research', 'study', 'analysis', 'experiment']):
            tags.append('academic')
        
        if any(word in text_content for word in ['business', 'market', 'revenue', 'profit']):
            tags.append('business')
        
        if any(word in text_content for word in ['technical', 'system', 'algorithm', 'implementation']):
            tags.append('technical')
        
        if any(word in text_content for word in ['medical', 'health', 'patient', 'treatment']):
            tags.append('medical')
        
        return list(set(tags))  # Remove duplicates
    
    def convert_batch(
        self,
        documents: List[Dict[str, Any]],
        batch_metadata: Optional[Dict[str, Any]] = None
    ) -> List[EpisodeContent]:
        """
        Convert multiple documents into episodes in batch.
        
        Args:
            documents: List of document dictionaries
            batch_metadata: Common metadata for the batch
            
        Returns:
            List of all episodes from all documents
        """
        all_episodes = []
        batch_meta = batch_metadata or {}
        
        for i, document in enumerate(documents):
            try:
                # Merge batch metadata with document metadata
                doc_metadata = {**batch_meta}
                if isinstance(document, dict) and 'metadata' in document:
                    doc_metadata.update(document['metadata'])
                
                doc_metadata['batch_index'] = i
                
                # Extract content
                content = document.get('content', document)
                
                # Convert document
                episodes = self.convert_document(content, doc_metadata)
                all_episodes.extend(episodes)
                
            except Exception as e:
                self.logger.error(f"Error converting document {i} in batch: {e}")
                continue
        
        self.logger.info(f"Batch conversion complete: {len(all_episodes)} episodes from {len(documents)} documents")
        return all_episodes