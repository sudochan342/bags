"""Key type detection for various blockchain formats."""

import re
import json
import base58
from enum import Enum
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

    # Patterns for extracting potential keys from messy text
    # Ethereum: 64 hex chars (with or without 0x)
    ETH_HEX_PATTERN = re.compile(r'(?:0x)?([a-fA-F0-9]{64})(?![a-fA-F0-9])')

    # Solana base58: 43-88 chars of base58 alphabet
    # 44 chars = public key, 64 chars = some formats, 87-88 = full keypair
    SOLANA_BASE58_PATTERN = re.compile(r'(?<![1-9A-HJ-NP-Za-km-z])([1-9A-HJ-NP-Za-km-z]{43,88})(?![1-9A-HJ-NP-Za-km-z])')

    # JSON array pattern for Solana keys
    JSON_ARRAY_PATTERN = re.compile(r'\[[\s\d,]+\]')

    @classmethod
    def detect_key_type(cls, value: str) -> KeyType:
        """
        Detect the type of key from its string representation.
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
        # Clean up - remove extra whitespace, common separators
        cleaned = re.sub(r'[,;|\-_]+', ' ', value)
        words = cleaned.lower().split()

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
        # Remove common prefixes/labels
        cleaned = re.sub(r'^.*?(?:key|pk|private|eth|evm|0x)[\s:=]*', '', value, flags=re.IGNORECASE)
        cleaned = cleaned.strip()

        # Check for 64 hex chars (with or without 0x)
        if cleaned.startswith('0x'):
            cleaned = cleaned[2:]

        if len(cleaned) == 64 and all(c in '0123456789abcdefABCDEF' for c in cleaned):
            return True

        return False

    @classmethod
    def _is_solana_private_key(cls, value: str) -> bool:
        """Check if value is a Solana private key."""
        # Check JSON array format first
        if '[' in value and ']' in value:
            try:
                # Extract JSON array from the line
                match = cls.JSON_ARRAY_PATTERN.search(value)
                if match:
                    arr = json.loads(match.group())
                    if len(arr) == 64 and all(isinstance(x, int) and 0 <= x <= 255 for x in arr):
                        return True
            except Exception:
                pass

        # Check base58 format - extract potential base58 string
        # Remove common labels
        cleaned = re.sub(r'^.*?(?:key|pk|private|sol|solana)[\s:=]*', '', value, flags=re.IGNORECASE)
        cleaned = cleaned.strip()

        # Try to find base58 string
        for candidate in [cleaned, value]:
            # Remove non-base58 chars from start/end
            candidate = candidate.strip()

            if len(candidate) >= 43 and len(candidate) <= 88:
                # Check if it's valid base58
                try:
                    decoded = base58.b58decode(candidate)
                    # Solana keypairs are 64 bytes, but we also accept 32 (seed)
                    if len(decoded) in [32, 64]:
                        return True
                except Exception:
                    pass

        return False

    @classmethod
    def _extract_eth_key(cls, line: str) -> str | None:
        """Try to extract an Ethereum private key from a messy line."""
        # First try direct match
        cleaned = line.strip()
        if cleaned.startswith('0x'):
            cleaned = cleaned[2:]
        if len(cleaned) == 64 and all(c in '0123456789abcdefABCDEF' for c in cleaned):
            return line.strip()

        # Try regex extraction
        match = cls.ETH_HEX_PATTERN.search(line)
        if match:
            hex_str = match.group(1)
            # Return with 0x prefix for consistency
            return '0x' + hex_str

        return None

    @classmethod
    def _extract_solana_key(cls, line: str) -> str | None:
        """Try to extract a Solana private key from a messy line."""
        # Check JSON array first
        if '[' in line and ']' in line:
            match = cls.JSON_ARRAY_PATTERN.search(line)
            if match:
                try:
                    arr = json.loads(match.group())
                    if len(arr) == 64 and all(isinstance(x, int) and 0 <= x <= 255 for x in arr):
                        return match.group()
                except Exception:
                    pass

        # Try base58 extraction
        matches = cls.SOLANA_BASE58_PATTERN.findall(line)
        for candidate in matches:
            try:
                decoded = base58.b58decode(candidate)
                if len(decoded) in [32, 64]:
                    return candidate
            except Exception:
                continue

        return None

    @classmethod
    def _extract_seed_phrase(cls, line: str) -> str | None:
        """Try to extract a seed phrase from a messy line."""
        # Clean up separators
        cleaned = re.sub(r'[,;|\-_]+', ' ', line)
        # Remove common labels
        cleaned = re.sub(r'^.*?(?:seed|mnemonic|phrase|words?)[\s:=]*', '', cleaned, flags=re.IGNORECASE)
        cleaned = ' '.join(cleaned.split())  # Normalize whitespace

        if cls._is_seed_phrase(cleaned):
            return cleaned

        # Try to find word sequences
        words = re.findall(r'\b([a-zA-Z]{3,8})\b', line)
        for start in range(len(words)):
            for count in cls.SEED_PHRASE_WORD_COUNTS:
                if start + count <= len(words):
                    candidate = ' '.join(words[start:start + count])
                    if cls._is_seed_phrase(candidate):
                        return candidate

        return None

    @classmethod
    def parse_keys_from_file(cls, filepath: str) -> list[DetectedKey]:
        """
        Parse a file and detect all keys with flexible extraction.
        """
        detected_keys = []

        with open(filepath, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith('#') or line.startswith('//'):
                    continue

                keys_found = cls._extract_keys_from_line(line, line_num)
                detected_keys.extend(keys_found)

        return detected_keys

    @classmethod
    def _extract_keys_from_line(cls, line: str, line_num: int) -> list[DetectedKey]:
        """Extract all possible keys from a single line."""
        found = []

        # Try seed phrase first (takes precedence - most words)
        seed = cls._extract_seed_phrase(line)
        if seed:
            found.append(DetectedKey(
                key_type=KeyType.SEED_PHRASE,
                raw_value=seed,
                line_number=line_num
            ))
            return found  # Seed phrase consumes the whole line

        # Try Ethereum key
        eth = cls._extract_eth_key(line)
        if eth:
            found.append(DetectedKey(
                key_type=KeyType.ETH_PRIVATE_KEY,
                raw_value=eth,
                line_number=line_num
            ))
            return found

        # Try Solana key
        sol = cls._extract_solana_key(line)
        if sol:
            found.append(DetectedKey(
                key_type=KeyType.SOLANA_PRIVATE_KEY,
                raw_value=sol,
                line_number=line_num
            ))
            return found

        return found

    @classmethod
    def parse_keys_from_text(cls, text: str) -> list[DetectedKey]:
        """
        Parse text content and detect all keys.
        """
        detected_keys = []

        for line_num, line in enumerate(text.strip().split('\n'), 1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#') or line.startswith('//'):
                continue

            keys_found = cls._extract_keys_from_line(line, line_num)
            detected_keys.extend(keys_found)

        return detected_keys
