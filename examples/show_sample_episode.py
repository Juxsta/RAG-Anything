#!/usr/bin/env python3
"""Show sample episode content from the textbook processing."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import PyPDF2
from raganything.episode_converter import EpisodeConverter

def main():
    pdf_path = "/home/ericreyes/github/RAG-Anything/Chapter2_Textbook.pdf"
    
    # Extract first page content
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        first_page = pdf_reader.pages[0]
        text = first_page.extract_text().strip()
    
    content_item = {
        "text": text,
        "page": 1,
        "title": "Chapter Title Page"
    }
    
    metadata = {
        "filename": "Chapter2_Textbook.pdf",
        "title": "Electromagnetics for Engineers - Chapter 2",
        "author": "Fawwaz Ulaby"
    }
    
    # Convert to episode
    converter = EpisodeConverter(
        default_group_id="electromagnetics_textbook",
        preserve_document_structure=True
    )
    
    episodes = converter.convert_document([content_item], metadata)
    
    if episodes:
        episode = episodes[0]
        print("=== SAMPLE EPISODE CONTENT ===")
        print(f"Episode Name: {episode.name}")
        print(f"Episode Type: {episode.episode_type}")
        print(f"Content Types: {[ct.value for ct in episode.content_types]}")
        print(f"Group ID: {episode.group_id}")
        print(f"UUID: {episode.uuid}")
        print(f"Source Description: {episode.source_description}")
        print(f"\nEpisode Body (first 500 chars):")
        print("-" * 50)
        print(episode.episode_body[:500] + "..." if len(episode.episode_body) > 500 else episode.episode_body)
        print("-" * 50)
        
        print(f"\nOriginal Metadata:")
        for key, value in episode.original_metadata.items():
            print(f"  {key}: {value}")

if __name__ == "__main__":
    main()