"""Key type detection for various blockchain formats."""

import re
import base64
import base58
from enum import Enum
from typing import Optional, Tuple
from dataclasses import dataclass


class KeyType(Enum):
    """Supported key types."""
    ETH_PRIVATE_KEY = "eth_private_key"
    SOLANA_PRIVATE_KEY = "solana_private_key"
    SEED_PHRASE = "seed_phrase"
    UNKNOWN = "unknown"


@dataclass
class DetectedKey:
    """Represents a detected key with its type and value."""
    key_type: KeyType
    raw_value: str
    line_number: int

    def __str__(self):
        truncated = self.raw_value[:20] + "..." if len(self.raw_value) > 20 else self.raw_value
        return f"{self.key_type.value}: {truncated} (line {self.line_number})"


class KeyDetector:
    """Detects and classifies various blockchain key formats."""

    # BIP-39 word list (partial for validation - we check word count and format)
    SEED_PHRASE_WORD_COUNTS = [12, 15, 18, 21, 24]

    # Ethereum private key pattern (64 hex chars, optionally with 0x prefix)
    ETH_PRIVATE_KEY_PATTERN = re.compile(r'^(0x)?[a-fA-F0-9]{64}$')

    # Solana private key patterns
    # Base58 encoded (87-88 chars typically)
    SOLANA_BASE58_PATTERN = re.compile(r'^[1-9A-HJ-NP-Za-km-z]{87,88}$')
    # JSON array format [1,2,3,...] (64 bytes)
    SOLANA_JSON_ARRAY_PATTERN = re.compile(r'^\s*\[\s*(\d+\s*,\s*){63}\d+\s*\]\s*$')

    @classmethod
    def detect_key_type(cls, value: str) -> KeyType:
        """
        Detect the type of key from its string representation.

        Args:
            value: The key string to analyze

        Returns:
            KeyType enum value
        """
        value = value.strip()

        if not value:
            return KeyType.UNKNOWN

        # Check for seed phrase first (12-24 words)
        if cls._is_seed_phrase(value):
            return KeyType.SEED_PHRASE

        # Check for Ethereum private key (64 hex chars)
        if cls._is_eth_private_key(value):
            return KeyType.ETH_PRIVATE_KEY

        # Check for Solana private key
        if cls._is_solana_private_key(value):
            return KeyType.SOLANA_PRIVATE_KEY

        return KeyType.UNKNOWN

    @classmethod
    def _is_seed_phrase(cls, value: str) -> bool:
        """Check if value looks like a BIP-39 seed phrase."""
        words = value.lower().split()

        # Must have valid word count
        if len(words) not in cls.SEED_PHRASE_WORD_COUNTS:
            return False

        # All words should be alphabetic and reasonable length
        for word in words:
            if not word.isalpha():
                return False
            if len(word) < 3 or len(word) > 8:
                return False

        return True

    @classmethod
    def _is_eth_private_key(cls, value: str) -> bool:
        """Check if value is an Ethereum private key."""
        return bool(cls.ETH_PRIVATE_KEY_PATTERN.match(value))

    @classmethod
    def _is_solana_private_key(cls, value: str) -> bool:
        """Check if value is a Solana private key."""
        # Check base58 format
        if cls.SOLANA_BASE58_PATTERN.match(value):
            try:
                decoded = base58.b58decode(value)
                # Solana keypairs are 64 bytes (32 private + 32 public)
                if len(decoded) == 64:
                    return True
            except Exception:
                pass

        # Check JSON array format
        if cls.SOLANA_JSON_ARRAY_PATTERN.match(value):
            try:
                import json
                arr = json.loads(value)
                if len(arr) == 64 and all(isinstance(x, int) and 0 <= x <= 255 for x in arr):
                    return True
            except Exception:
                pass

        return False

    @classmethod
    def parse_keys_from_file(cls, filepath: str) -> list[DetectedKey]:
        """
        Parse a file and detect all keys.

        Args:
            filepath: Path to the file containing keys

        Returns:
            List of DetectedKey objects
        """
        detected_keys = []

        with open(filepath, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue

                key_type = cls.detect_key_type(line)

                if key_type != KeyType.UNKNOWN:
                    detected_keys.append(DetectedKey(
                        key_type=key_type,
                        raw_value=line,
                        line_number=line_num
                    ))

        return detected_keys

    @classmethod
    def parse_keys_from_text(cls, text: str) -> list[DetectedKey]:
        """
        Parse text content and detect all keys.

        Args:
            text: Text content containing keys (one per line)

        Returns:
            List of DetectedKey objects
        """
        detected_keys = []

        for line_num, line in enumerate(text.strip().split('\n'), 1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            key_type = cls.detect_key_type(line)

            if key_type != KeyType.UNKNOWN:
                detected_keys.append(DetectedKey(
                    key_type=key_type,
                    raw_value=line,
                    line_number=line_num
                ))

        return detected_keys
