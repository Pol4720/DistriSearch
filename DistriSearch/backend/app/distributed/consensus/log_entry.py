"""
Log Entry Management for Raft.

Implements the replicated log data structure and storage.
Each entry contains a command to be applied to the state machine.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class LogEntry:
    """
    A single entry in the Raft log.
    
    Attributes:
        index: Position in the log (1-indexed)
        term: Term when entry was received by leader
        command: Command to apply to state machine
        timestamp: When the entry was created
    """
    index: int
    term: int
    command: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "index": self.index,
            "term": self.term,
            "command": self.command,
            "timestamp": self.timestamp.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogEntry":
        """Create from dictionary."""
        return cls(
            index=data["index"],
            term=data["term"],
            command=data["command"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )
    
    def __eq__(self, other: object) -> bool:
        """Check equality based on index and term."""
        if not isinstance(other, LogEntry):
            return False
        return self.index == other.index and self.term == other.term


class LogStore:
    """
    Persistent storage for Raft log entries.
    
    The log is append-only with support for truncation
    during leader conflicts.
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize log store.
        
        Args:
            storage_path: Path for persistent log storage
        """
        self.storage_path = storage_path
        self._entries: List[LogEntry] = []
        self._lock = asyncio.Lock()
        
        # Snapshot state
        self._snapshot_index: int = 0
        self._snapshot_term: int = 0
    
    @property
    def last_index(self) -> int:
        """Get index of last log entry (0 if empty)."""
        if not self._entries:
            return self._snapshot_index
        return self._entries[-1].index
    
    @property
    def last_term(self) -> int:
        """Get term of last log entry (0 if empty)."""
        if not self._entries:
            return self._snapshot_term
        return self._entries[-1].term
    
    @property
    def length(self) -> int:
        """Get number of entries in log."""
        return len(self._entries)
    
    async def initialize(self):
        """Load log entries from storage."""
        if self.storage_path:
            try:
                await self._load_from_disk()
            except Exception as e:
                logger.warning(f"Could not load log from disk: {e}")
    
    async def _load_from_disk(self):
        """Load log entries from disk storage."""
        if not self.storage_path:
            return
            
        log_file = self.storage_path / "log.json"
        if log_file.exists():
            async with self._lock:
                data = json.loads(log_file.read_text())
                self._entries = [
                    LogEntry.from_dict(entry)
                    for entry in data.get("entries", [])
                ]
                self._snapshot_index = data.get("snapshot_index", 0)
                self._snapshot_term = data.get("snapshot_term", 0)
                
                logger.info(
                    f"Loaded {len(self._entries)} log entries, "
                    f"last_index={self.last_index}"
                )
    
    async def _save_to_disk(self):
        """Save log entries to disk storage."""
        if not self.storage_path:
            return
            
        self.storage_path.mkdir(parents=True, exist_ok=True)
        log_file = self.storage_path / "log.json"
        
        data = {
            "entries": [entry.to_dict() for entry in self._entries],
            "snapshot_index": self._snapshot_index,
            "snapshot_term": self._snapshot_term,
        }
        log_file.write_text(json.dumps(data))
    
    async def append(self, command: Dict[str, Any], term: int) -> LogEntry:
        """
        Append a new entry to the log.
        
        Args:
            command: Command to store
            term: Current term
            
        Returns:
            The created LogEntry
        """
        async with self._lock:
            new_index = self.last_index + 1
            entry = LogEntry(
                index=new_index,
                term=term,
                command=command,
            )
            self._entries.append(entry)
            await self._save_to_disk()
            
            logger.debug(f"Appended log entry {new_index} in term {term}")
            return entry
    
    async def append_entries(
        self,
        entries: List[LogEntry],
        prev_log_index: int,
        prev_log_term: int,
    ) -> bool:
        """
        Append entries from leader (for followers).
        
        Implements the log consistency check:
        1. If log doesn't contain entry at prev_log_index with prev_log_term, return False
        2. If existing entry conflicts with new entry, delete existing and all following
        3. Append any new entries not in log
        
        Args:
            entries: Entries to append
            prev_log_index: Index of log entry immediately preceding new ones
            prev_log_term: Term of prev_log_index entry
            
        Returns:
            True if entries were appended successfully
        """
        async with self._lock:
            # Check if we have the previous entry
            if prev_log_index > 0:
                prev_entry = self._get_entry_unsafe(prev_log_index)
                if prev_entry is None or prev_entry.term != prev_log_term:
                    logger.debug(
                        f"Log consistency check failed: "
                        f"prev_index={prev_log_index}, prev_term={prev_log_term}"
                    )
                    return False
            
            # Process each entry
            for entry in entries:
                existing = self._get_entry_unsafe(entry.index)
                
                if existing is not None:
                    if existing.term != entry.term:
                        # Conflict: delete existing entry and all that follow
                        self._truncate_from_unsafe(entry.index)
                        self._entries.append(entry)
                    # else: entry already exists and matches, skip
                else:
                    # New entry
                    self._entries.append(entry)
            
            await self._save_to_disk()
            return True
    
    def _get_entry_unsafe(self, index: int) -> Optional[LogEntry]:
        """Get entry by index without lock (internal use)."""
        if index <= self._snapshot_index:
            return None
            
        # Convert to list index
        list_index = index - self._snapshot_index - 1
        if 0 <= list_index < len(self._entries):
            return self._entries[list_index]
        return None
    
    def _truncate_from_unsafe(self, index: int):
        """Truncate log from index onwards without lock (internal use)."""
        if index <= self._snapshot_index:
            self._entries = []
            return
            
        list_index = index - self._snapshot_index - 1
        if list_index >= 0:
            self._entries = self._entries[:list_index]
            logger.info(f"Log truncated from index {index}")
    
    async def get_entry(self, index: int) -> Optional[LogEntry]:
        """
        Get entry by index.
        
        Args:
            index: The log index (1-indexed)
            
        Returns:
            The entry or None if not found
        """
        async with self._lock:
            return self._get_entry_unsafe(index)
    
    async def get_entries_from(
        self,
        start_index: int,
        max_entries: int = 100,
    ) -> List[LogEntry]:
        """
        Get entries starting from an index.
        
        Args:
            start_index: Starting index (inclusive)
            max_entries: Maximum entries to return
            
        Returns:
            List of entries
        """
        async with self._lock:
            result = []
            for i in range(start_index, start_index + max_entries):
                entry = self._get_entry_unsafe(i)
                if entry is None:
                    break
                result.append(entry)
            return result
    
    async def get_term_at_index(self, index: int) -> int:
        """
        Get term of entry at index.
        
        Args:
            index: The log index
            
        Returns:
            Term at index, 0 if index <= snapshot or not found
        """
        if index <= 0:
            return 0
        if index == self._snapshot_index:
            return self._snapshot_term
            
        async with self._lock:
            entry = self._get_entry_unsafe(index)
            return entry.term if entry else 0
    
    async def get_entries_for_commit(
        self,
        start_index: int,
        end_index: int,
    ) -> List[LogEntry]:
        """
        Get entries in range for applying to state machine.
        
        Args:
            start_index: Start index (inclusive)
            end_index: End index (inclusive)
            
        Returns:
            List of entries in range
        """
        async with self._lock:
            result = []
            for i in range(start_index, end_index + 1):
                entry = self._get_entry_unsafe(i)
                if entry:
                    result.append(entry)
            return result
    
    async def create_snapshot(self, last_included_index: int, last_included_term: int):
        """
        Create a snapshot up to the given index.
        
        Discards log entries up to and including last_included_index.
        
        Args:
            last_included_index: Index of last entry to include in snapshot
            last_included_term: Term of last_included_index entry
        """
        async with self._lock:
            if last_included_index <= self._snapshot_index:
                return
            
            # Calculate entries to keep
            list_index = last_included_index - self._snapshot_index
            self._entries = self._entries[list_index:]
            
            self._snapshot_index = last_included_index
            self._snapshot_term = last_included_term
            
            await self._save_to_disk()
            
            logger.info(
                f"Created snapshot at index {last_included_index}, "
                f"term {last_included_term}"
            )
    
    async def match_term_at_index(self, index: int, term: int) -> bool:
        """
        Check if log contains entry with given index and term.
        
        Args:
            index: The log index
            term: The expected term
            
        Returns:
            True if entry exists with matching term
        """
        if index == 0:
            return term == 0
        if index == self._snapshot_index:
            return term == self._snapshot_term
            
        entry = await self.get_entry(index)
        return entry is not None and entry.term == term
    
    def get_status(self) -> Dict[str, Any]:
        """Get log status for monitoring."""
        return {
            "length": len(self._entries),
            "last_index": self.last_index,
            "last_term": self.last_term,
            "snapshot_index": self._snapshot_index,
            "snapshot_term": self._snapshot_term,
        }
