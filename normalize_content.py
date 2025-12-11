"""
normalize_content.py — Normalize and process content blocks from extracted manifest

This module handles:
- Normalizing content structure for database storage
- Copying media files to appropriate locations
- Processing node content (paragraphs, tables, images, etc.)
"""

from typing import List, Dict, Any, Optional
import os
import json


def normalize_content_and_copy_media(
    content_list: List[Dict[str, Any]], 
    media_src_dir: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Normalize content blocks and copy referenced media files.
    
    Args:
        content_list: List of content blocks from extracted manifest
                     Each block has 'type' (question_text, table, figure, etc)
                     and type-specific data
        media_src_dir: Optional source directory for media files to copy from
    
    Returns:
        Normalized content list ready for database storage
    
    Examples:
        >>> content = [
        ...     {'type': 'question_text', 'text': 'What is 2+2?'},
        ...     {'type': 'table', 'rows': [['A', 'B'], ['1', '2']]},
        ...     {'type': 'figure', 'images': ['image_abc123.png'], 'caption': 'Fig 1'}
        ... ]
        >>> normalized = normalize_content_and_copy_media(content)
    """
    if not content_list:
        return []
    
    normalized = []
    
    for block in content_list:
        if not isinstance(block, dict):
            continue
        
        block_type = block.get('type', 'paragraph')
        
        # Create normalized block based on type
        normalized_block = {
            'type': block_type,
        }
        
        if block_type in ('question_text', 'paragraph'):
            # Text blocks: preserve text
            normalized_block['text'] = block.get('text', '')
        
        elif block_type == 'table':
            # Table blocks: preserve rows structure
            normalized_block['rows'] = block.get('rows', [])
        
        elif block_type == 'figure':
            # Figure blocks: images + caption
            normalized_block['images'] = block.get('images', [])
            if block.get('caption'):
                normalized_block['caption'] = block.get('caption')
            
            # TODO: Copy media files if media_src_dir provided
            if media_src_dir:
                images = block.get('images', [])
                # copy_media_files(images, media_src_dir)
                pass
        
        elif block_type == 'pagebreak':
            # Page breaks: no additional data
            pass
        
        else:
            # Generic: preserve as-is
            normalized_block.update(block)
        
        normalized.append(normalized_block)
    
    return normalized


def copy_media_files(
    image_filenames: List[str],
    src_dir: str,
    dst_dir: Optional[str] = None
) -> bool:
    """
    Copy media files from source to destination directory.
    
    Args:
        image_filenames: List of image filenames to copy
        src_dir: Source directory containing images
        dst_dir: Destination directory (optional)
    
    Returns:
        True if all files copied successfully, False otherwise
    """
    if not dst_dir or not os.path.isdir(src_dir):
        return False
    
    try:
        os.makedirs(dst_dir, exist_ok=True)
        
        for filename in image_filenames:
            if not filename:
                continue
            
            src_path = os.path.join(src_dir, filename)
            dst_path = os.path.join(dst_dir, filename)
            
            # Skip if already exists
            if os.path.exists(dst_path):
                continue
            
            # Copy file
            if os.path.isfile(src_path):
                with open(src_path, 'rb') as src:
                    with open(dst_path, 'wb') as dst:
                        dst.write(src.read())
        
        return True
    except Exception as e:
        print(f"Error copying media files: {e}")
        return False