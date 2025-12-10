"""
Input Validators
Validation utilities for DistriSearch API inputs
"""

from typing import Optional, List, Dict, Any
import re
import html
import logging

from .exceptions import ValidationError

logger = logging.getLogger(__name__)


# Constants
MAX_DOCUMENT_CONTENT_LENGTH = 10_000_000  # 10MB
MAX_TITLE_LENGTH = 500
MAX_QUERY_LENGTH = 1000
MIN_QUERY_LENGTH = 1
MAX_TAGS = 50
MAX_TAG_LENGTH = 100
MAX_METADATA_SIZE = 100_000  # 100KB


def validate_document_content(content: str, max_length: int = MAX_DOCUMENT_CONTENT_LENGTH) -> str:
    """
    Validate document content.
    
    Args:
        content: Document content string
        max_length: Maximum allowed length
    
    Returns:
        Validated and cleaned content
    
    Raises:
        ValidationError: If validation fails
    """
    if not content:
        raise ValidationError("Document content cannot be empty", field="content")
    
    if not isinstance(content, str):
        raise ValidationError("Document content must be a string", field="content")
    
    # Check length
    if len(content) > max_length:
        raise ValidationError(
            f"Document content exceeds maximum length of {max_length} characters",
            field="content",
            value=f"{len(content)} characters"
        )
    
    # Strip leading/trailing whitespace
    content = content.strip()
    
    if not content:
        raise ValidationError(
            "Document content cannot be empty or whitespace only",
            field="content"
        )
    
    return content


def validate_document_title(title: str, max_length: int = MAX_TITLE_LENGTH) -> str:
    """
    Validate document title.
    
    Args:
        title: Document title string
        max_length: Maximum allowed length
    
    Returns:
        Validated and cleaned title
    
    Raises:
        ValidationError: If validation fails
    """
    if not title:
        raise ValidationError("Document title cannot be empty", field="title")
    
    if not isinstance(title, str):
        raise ValidationError("Document title must be a string", field="title")
    
    # Strip whitespace
    title = title.strip()
    
    if not title:
        raise ValidationError(
            "Document title cannot be empty or whitespace only",
            field="title"
        )
    
    if len(title) > max_length:
        raise ValidationError(
            f"Document title exceeds maximum length of {max_length} characters",
            field="title",
            value=f"{len(title)} characters"
        )
    
    return title


def validate_search_query(
    query: str,
    min_length: int = MIN_QUERY_LENGTH,
    max_length: int = MAX_QUERY_LENGTH
) -> str:
    """
    Validate search query.
    
    Args:
        query: Search query string
        min_length: Minimum allowed length
        max_length: Maximum allowed length
    
    Returns:
        Validated and cleaned query
    
    Raises:
        ValidationError: If validation fails
    """
    if not query:
        raise ValidationError("Search query cannot be empty", field="query")
    
    if not isinstance(query, str):
        raise ValidationError("Search query must be a string", field="query")
    
    # Strip whitespace
    query = query.strip()
    
    if len(query) < min_length:
        raise ValidationError(
            f"Search query must be at least {min_length} character(s)",
            field="query"
        )
    
    if len(query) > max_length:
        raise ValidationError(
            f"Search query exceeds maximum length of {max_length} characters",
            field="query",
            value=f"{len(query)} characters"
        )
    
    # Check for potential injection patterns
    if _contains_injection_pattern(query):
        logger.warning(f"Potential injection detected in query: {query[:100]}")
        # Don't reject, just sanitize
        query = sanitize_input(query)
    
    return query


def validate_node_id(node_id: str) -> str:
    """
    Validate node ID.
    
    Args:
        node_id: Node identifier
    
    Returns:
        Validated node ID
    
    Raises:
        ValidationError: If validation fails
    """
    if not node_id:
        raise ValidationError("Node ID cannot be empty", field="node_id")
    
    if not isinstance(node_id, str):
        raise ValidationError("Node ID must be a string", field="node_id")
    
    # Strip whitespace
    node_id = node_id.strip()
    
    # Validate format (alphanumeric with hyphens and underscores)
    if not re.match(r'^[a-zA-Z0-9_-]+$', node_id):
        raise ValidationError(
            "Node ID can only contain alphanumeric characters, hyphens, and underscores",
            field="node_id",
            value=node_id
        )
    
    if len(node_id) > 100:
        raise ValidationError(
            "Node ID exceeds maximum length of 100 characters",
            field="node_id"
        )
    
    return node_id


def validate_document_id(document_id: str) -> str:
    """
    Validate document ID (UUID format).
    
    Args:
        document_id: Document identifier
    
    Returns:
        Validated document ID
    
    Raises:
        ValidationError: If validation fails
    """
    if not document_id:
        raise ValidationError("Document ID cannot be empty", field="document_id")
    
    # UUID format: 8-4-4-4-12 hexadecimal characters
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    
    if not re.match(uuid_pattern, document_id.lower()):
        raise ValidationError(
            "Document ID must be a valid UUID",
            field="document_id",
            value=document_id
        )
    
    return document_id.lower()


def validate_tags(tags: List[str], max_tags: int = MAX_TAGS) -> List[str]:
    """
    Validate document tags.
    
    Args:
        tags: List of tag strings
        max_tags: Maximum number of tags
    
    Returns:
        Validated and cleaned tags
    
    Raises:
        ValidationError: If validation fails
    """
    if not tags:
        return []
    
    if not isinstance(tags, list):
        raise ValidationError("Tags must be a list", field="tags")
    
    if len(tags) > max_tags:
        raise ValidationError(
            f"Too many tags. Maximum is {max_tags}",
            field="tags",
            value=f"{len(tags)} tags"
        )
    
    cleaned_tags = []
    for i, tag in enumerate(tags):
        if not isinstance(tag, str):
            raise ValidationError(
                f"Tag at index {i} must be a string",
                field=f"tags[{i}]"
            )
        
        tag = tag.strip().lower()
        
        if not tag:
            continue  # Skip empty tags
        
        if len(tag) > MAX_TAG_LENGTH:
            raise ValidationError(
                f"Tag at index {i} exceeds maximum length of {MAX_TAG_LENGTH}",
                field=f"tags[{i}]"
            )
        
        # Only allow alphanumeric, hyphens, underscores, and spaces
        if not re.match(r'^[a-zA-Z0-9_\- ]+$', tag):
            raise ValidationError(
                f"Tag '{tag}' contains invalid characters",
                field=f"tags[{i}]"
            )
        
        cleaned_tags.append(tag)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_tags = []
    for tag in cleaned_tags:
        if tag not in seen:
            seen.add(tag)
            unique_tags.append(tag)
    
    return unique_tags


def validate_metadata(
    metadata: Dict[str, Any],
    max_size: int = MAX_METADATA_SIZE
) -> Dict[str, Any]:
    """
    Validate document metadata.
    
    Args:
        metadata: Metadata dictionary
        max_size: Maximum serialized size in bytes
    
    Returns:
        Validated metadata
    
    Raises:
        ValidationError: If validation fails
    """
    if not metadata:
        return {}
    
    if not isinstance(metadata, dict):
        raise ValidationError("Metadata must be a dictionary", field="metadata")
    
    # Check size
    import json
    try:
        serialized = json.dumps(metadata)
        if len(serialized) > max_size:
            raise ValidationError(
                f"Metadata exceeds maximum size of {max_size} bytes",
                field="metadata"
            )
    except (TypeError, ValueError) as e:
        raise ValidationError(
            f"Metadata contains non-serializable values: {e}",
            field="metadata"
        )
    
    # Recursively validate and sanitize
    return _sanitize_dict(metadata)


def sanitize_input(text: str) -> str:
    """
    Sanitize text input to prevent XSS and other injection attacks.
    
    Args:
        text: Input text
    
    Returns:
        Sanitized text
    """
    if not text:
        return text
    
    # HTML escape
    text = html.escape(text)
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Remove control characters except newlines and tabs
    text = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    
    return text


def sanitize_html(html_content: str) -> str:
    """
    Sanitize HTML content, removing potentially dangerous elements.
    
    Args:
        html_content: HTML string
    
    Returns:
        Sanitized HTML string
    """
    # Remove script tags and their content
    html_content = re.sub(
        r'<script[^>]*>.*?</script>',
        '',
        html_content,
        flags=re.DOTALL | re.IGNORECASE
    )
    
    # Remove style tags and their content
    html_content = re.sub(
        r'<style[^>]*>.*?</style>',
        '',
        html_content,
        flags=re.DOTALL | re.IGNORECASE
    )
    
    # Remove event handlers
    html_content = re.sub(
        r'\s+on\w+\s*=\s*["\'][^"\']*["\']',
        '',
        html_content,
        flags=re.IGNORECASE
    )
    
    # Remove javascript: URLs
    html_content = re.sub(
        r'javascript\s*:',
        '',
        html_content,
        flags=re.IGNORECASE
    )
    
    # Remove data: URLs (potential XSS vector)
    html_content = re.sub(
        r'data\s*:',
        '',
        html_content,
        flags=re.IGNORECASE
    )
    
    return html_content


def _contains_injection_pattern(text: str) -> bool:
    """Check if text contains potential injection patterns."""
    # Common injection patterns
    patterns = [
        r'<script',
        r'javascript:',
        r'on\w+\s*=',
        r'\$\{',  # Template injection
        r'\{\{',  # Template injection
        r'<%',    # ASP/JSP injection
        r'eval\s*\(',
        r'exec\s*\(',
    ]
    
    text_lower = text.lower()
    for pattern in patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    
    return False


def _sanitize_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively sanitize a dictionary."""
    result = {}
    
    for key, value in d.items():
        # Sanitize key
        if isinstance(key, str):
            key = sanitize_input(key)
        
        # Sanitize value
        if isinstance(value, str):
            value = sanitize_input(value)
        elif isinstance(value, dict):
            value = _sanitize_dict(value)
        elif isinstance(value, list):
            value = _sanitize_list(value)
        
        result[key] = value
    
    return result


def _sanitize_list(lst: List[Any]) -> List[Any]:
    """Recursively sanitize a list."""
    result = []
    
    for item in lst:
        if isinstance(item, str):
            item = sanitize_input(item)
        elif isinstance(item, dict):
            item = _sanitize_dict(item)
        elif isinstance(item, list):
            item = _sanitize_list(item)
        
        result.append(item)
    
    return result


def validate_pagination(
    page: int,
    page_size: int,
    max_page_size: int = 100
) -> tuple:
    """
    Validate pagination parameters.
    
    Args:
        page: Page number (1-indexed)
        page_size: Items per page
        max_page_size: Maximum allowed page size
    
    Returns:
        Tuple of (validated_page, validated_page_size)
    
    Raises:
        ValidationError: If validation fails
    """
    if page < 1:
        raise ValidationError(
            "Page number must be at least 1",
            field="page",
            value=page
        )
    
    if page_size < 1:
        raise ValidationError(
            "Page size must be at least 1",
            field="page_size",
            value=page_size
        )
    
    if page_size > max_page_size:
        raise ValidationError(
            f"Page size cannot exceed {max_page_size}",
            field="page_size",
            value=page_size
        )
    
    return page, page_size


def validate_file_extension(
    filename: str,
    allowed_extensions: List[str]
) -> bool:
    """
    Validate file extension.
    
    Args:
        filename: Name of the file
        allowed_extensions: List of allowed extensions (e.g., ['.pdf', '.docx'])
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If extension is not allowed
    """
    if not filename:
        raise ValidationError("Filename cannot be empty", field="filename")
    
    import os
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in allowed_extensions:
        raise ValidationError(
            f"File extension '{ext}' is not allowed. Allowed: {', '.join(allowed_extensions)}",
            field="filename",
            value=filename
        )
    
    return True


def validate_url(url: str) -> str:
    """
    Validate URL format.
    
    Args:
        url: URL string
    
    Returns:
        Validated URL
    
    Raises:
        ValidationError: If URL is invalid
    """
    import urllib.parse
    
    if not url:
        raise ValidationError("URL cannot be empty", field="url")
    
    try:
        parsed = urllib.parse.urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid URL")
        
        if parsed.scheme not in ['http', 'https']:
            raise ValidationError(
                "URL must use http or https scheme",
                field="url",
                value=url
            )
        
        return url
    except Exception as e:
        raise ValidationError(
            f"Invalid URL format: {str(e)}",
            field="url",
            value=url
        )
