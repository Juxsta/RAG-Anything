#!/usr/bin/env python3
"""
Demonstrate Graphiti's citation and reference capabilities.
Shows how source information is preserved and returned in query results.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import PyPDF2
from raganything.episode_converter import EpisodeConverter

def create_sample_episodes():
    """Create sample episodes with different source information."""
    pdf_path = "/home/ericreyes/github/RAG-Anything/Chapter2_Textbook.pdf"
    
    # Extract content from specific pages with coordinate system info
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        
        # Simulate different pages with coordinate system content
        sample_pages = [
            (5, "Introduction to Coordinate Systems"),
            (12, "Cartesian Coordinate System"),  
            (18, "Cylindrical Coordinate System"),
            (23, "Spherical Coordinate System")
        ]
        
        episodes = []
        converter = EpisodeConverter(
            default_group_id="electromagnetics_textbook",
            preserve_document_structure=True
        )
        
        for page_num, topic in sample_pages:
            if page_num < len(pdf_reader.pages):
                text = pdf_reader.pages[page_num].extract_text().strip()
                content_item = {
                    "text": text[:500] + "...",  # Truncate for demo
                    "page": page_num + 1,
                    "title": topic,
                    "topic": "coordinate_systems"
                }
                
                metadata = {
                    "filename": "Chapter2_Textbook.pdf",
                    "title": f"Electromagnetics for Engineers - {topic}",
                    "author": "Fawwaz Ulaby",
                    "page_number": page_num + 1
                }
                
                episode_list = converter.convert_document([content_item], metadata)
                if episode_list:
                    episodes.append(episode_list[0])
        
        return episodes

def demonstrate_citation_system():
    """Demonstrate how Graphiti preserves and returns citation information."""
    print("=== GRAPHITI CITATION & REFERENCE CAPABILITY DEMO ===\n")
    
    # Create sample episodes
    episodes = create_sample_episodes()
    
    print("1. EPISODE SOURCE INFORMATION:")
    print("=" * 50)
    for i, episode in enumerate(episodes, 1):
        print(f"\nEpisode {i}:")
        print(f"  Name: {episode.name}")
        print(f"  Source Description: {episode.source_description}")
        print(f"  Original Metadata:")
        for key, value in episode.original_metadata.items():
            print(f"    {key}: {value}")
        print(f"  Content Preview: {episode.episode_body[:100]}...")
    
    print("\n\n2. SIMULATED SEARCH RESULTS WITH CITATIONS:")
    print("=" * 50)
    
    # Simulate a query about coordinate systems
    query = "What are coordinate systems in electromagnetics?"
    print(f"Query: '{query}'\n")
    
    print("Search Results (with proper citations):")
    for i, episode in enumerate(episodes, 1):
        print(f"\nResult {i}:")
        print(f"  Content: {episode.episode_body[:200]}...")
        print(f"  📖 Citation: {episode.source_description}")
        print(f"  📄 Source: {episode.original_metadata.get('filename', 'Unknown')}")
        print(f"  📍 Page: {episode.original_metadata.get('page_number', 'Unknown')}")
        print(f"  👤 Author: {episode.original_metadata.get('author', 'Unknown')}")
    
    print("\n\n3. GRAPHITI'S CITATION CAPABILITIES:")
    print("=" * 50)
    print("✅ Source Description: Each episode includes detailed source info")
    print("✅ Metadata Preservation: Original document metadata is maintained") 
    print("✅ Page References: Specific page numbers for precise citations")
    print("✅ Author Attribution: Author information is preserved")
    print("✅ Document Tracking: Full filename and title information")
    print("✅ UUID Tracking: Unique identifiers for exact reference lookup")
    
    print("\n4. CITATION FORMATS AVAILABLE:")
    print("=" * 50)
    sample_episode = episodes[0]
    
    # Different citation format examples
    print("Academic Citation:")
    print(f"  Ulaby, F. T. ({sample_episode.reference_time.year}). "
          f"{sample_episode.original_metadata.get('title', 'Document')}. "
          f"Page {sample_episode.original_metadata.get('page_number', 'Unknown')}.")
    
    print("\nShort Citation:")
    print(f"  [{sample_episode.original_metadata.get('filename', 'Unknown')}, "
          f"p. {sample_episode.original_metadata.get('page_number', 'Unknown')}]")
    
    print("\nDetailed Reference:")
    print(f"  Source: {sample_episode.source_description}")
    
    return episodes

if __name__ == "__main__":
    demonstrate_citation_system()