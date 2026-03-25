"""
Fuzzy Matching Engine for Blender MCP 1.0.0

Provides intelligent fuzzy matching for:
- Object names
- Property paths
- Action names
- Brush names
- Material names
- Multi-language support with phonetic matching

High Mode Philosophy: Understand user intent, not just literal input.
"""

import re
from typing import Any, DefaultDict, Dict, List, Optional, Tuple
from difflib import SequenceMatcher
from collections import defaultdict


class FuzzyMatcher:
    """
    Advanced fuzzy matching with multi-strategy scoring.
    """

    def __init__(
        self, threshold: float = 0.6, case_sensitive: bool = False, cache_size: int = 1000
    ) -> None:
        self.threshold = threshold
        self.case_sensitive = case_sensitive
        self._cache: Dict[str, List[Tuple[str, float]]] = {}
        self._cache_size = cache_size
        self._access_order: List[str] = []

        # Scoring weights
        self.weights = {
            "exact": 1.0,
            "starts_with": 0.95,
            "word_start": 0.9,
            "contains": 0.8,
            "fuzzy": 0.7,
            "phonetic": 0.6,
        }

    def _normalize(self, text: str) -> str:
        """Normalize text for comparison."""
        if not text:
            return ""
        if not self.case_sensitive:
            text = text.lower()
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _get_cache_key(self, query: str, candidates_tuple: Tuple[str, ...]) -> str:
        """Generate cache key."""
        return f"{self._normalize(query)}:{hash(candidates_tuple)}"

    def _update_cache(self, key: str, value: Any) -> None:
        """Update LRU cache."""
        if key in self._cache:
            self._access_order.remove(key)
        elif len(self._cache) >= self._cache_size:
            # Remove oldest
            oldest = self._access_order.pop(0)
            del self._cache[oldest]

        self._cache[key] = value
        self._access_order.append(key)

    def match(
        self,
        query: str,
        candidates: List[str],
        limit: int = 10,
        min_score: Optional[float] = None,
    ) -> List[Tuple[str, float]]:
        """
        Find matches for query in candidates.

        Args:
            query: Search query
            candidates: List of candidate strings
            limit: Maximum number of results
            min_score: Minimum score threshold (default: self.threshold)

        Returns:
            List of (candidate, score) tuples, sorted by score descending
        """
        if not query or not candidates:
            return []

        min_score = self.threshold if min_score is None else min_score
        query_norm = self._normalize(query)

        # Check cache
        cache_key = self._get_cache_key(query, tuple(candidates))
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            return [(c, s) for c, s in cached if s >= min_score][:limit]

        results: List[Tuple[str, float]] = []

        for candidate in candidates:
            if not candidate:
                continue

            candidate_norm = self._normalize(candidate)
            score = self._calculate_score(query_norm, candidate_norm)

            if score >= min_score:
                results.append((candidate, score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)

        # Cache results
        self._update_cache(cache_key, results)

        return results[:limit]

    def best_match(
        self,
        query: str,
        candidates: List[str],
        min_score: Optional[float] = None,
    ) -> Optional[Tuple[str, float]]:
        """
        Get single best match.

        Returns:
            (candidate, score) tuple or None
        """
        results = self.match(query, candidates, limit=1, min_score=min_score)
        return results[0] if results else None

    def _calculate_score(self, query: str, candidate: str) -> float:
        """
        Calculate match score using multiple strategies.
        """
        if not query or not candidate:
            return 0.0

        scores = []

        # 1. Exact match (highest priority)
        if query == candidate:
            return self.weights["exact"]

        # 2. Starts with
        if candidate.startswith(query):
            # Boost for longer matches
            length_bonus = len(query) / len(candidate) * 0.05
            scores.append(self.weights["starts_with"] + length_bonus)

        # 3. Word start matching (e.g., "LD" matches "Light Direction")
        word_initials = "".join(word[0] for word in candidate.split() if word)
        if query == word_initials:
            scores.append(self.weights["word_start"])
        elif word_initials.startswith(query):
            scores.append(self.weights["word_start"] * 0.9)

        # 4. Contains (substring)
        if query in candidate:
            # Position bonus (earlier is better)
            position = candidate.index(query)
            position_bonus = (len(candidate) - position) / len(candidate) * 0.1
            scores.append(self.weights["contains"] + position_bonus)

        # 5. Fuzzy string matching
        fuzzy_score = SequenceMatcher(None, query, candidate).ratio()
        if fuzzy_score >= self.threshold:
            scores.append(self.weights["fuzzy"] * fuzzy_score)

        # 6. Token-based matching
        token_score = self._token_match_score(query, candidate)
        if token_score > 0:
            scores.append(token_score * 0.85)

        return max(scores) if scores else 0.0

    def _token_match_score(self, query: str, candidate: str) -> float:
        """Calculate token-based match score."""
        query_tokens = set(query.split())
        candidate_tokens = set(candidate.split())

        if not query_tokens or not candidate_tokens:
            return 0.0

        # Calculate Jaccard similarity
        intersection = len(query_tokens & candidate_tokens)
        union = len(query_tokens | candidate_tokens)

        if union == 0:
            return 0.0

        return intersection / union

    def filter(
        self,
        query: str,
        candidates: List[str],
        min_score: Optional[float] = None,
    ) -> List[str]:
        """
        Filter candidates by match score.

        Returns only the candidate strings that match.
        """
        matches = self.match(query, candidates, min_score=min_score)
        return [c for c, _ in matches]

    def rank(self, query: str, candidates: List[str]) -> List[Tuple[str, float]]:
        """
        Rank all candidates by relevance to query.

        Returns all candidates with scores, sorted by score.
        """
        return self.match(query, candidates, limit=len(candidates), min_score=0.0)


class MultiFieldMatcher:
    """
    Fuzzy matcher that searches across multiple fields of objects.
    """

    def __init__(self, threshold: float = 0.6) -> None:
        self.matcher = FuzzyMatcher(threshold=threshold)
        self.field_weights: DefaultDict[str, float] = defaultdict(lambda: 1.0)

    def set_field_weight(self, field: str, weight: float) -> None:
        """Set weight for specific field."""
        self.field_weights[field] = weight

    def match(
        self, query: str, items: List[Dict[str, Any]], fields: List[str], limit: int = 10
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Search across multiple fields.

        Args:
            query: Search query
            items: List of dictionaries to search
            fields: Field names to search
            limit: Maximum results

        Returns:
            List of (item, score) tuples
        """
        if not query or not items:
            return []

        results = []

        for item in items:
            best_score = 0.0

            for field in fields:
                if field not in item:
                    continue

                value = str(item[field])
                match_result = self.matcher.best_match(query, [value])

                if match_result:
                    _, score = match_result
                    weighted_score = score * self.field_weights[field]
                    best_score = max(best_score, weighted_score)

            if best_score >= self.matcher.threshold:
                results.append((item, best_score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]


class PhoneticMatcher:
    """
    Phonetic matching for name-based searches.
    Useful for matching spoken/natural language input.
    """

    def __init__(self) -> None:
        self.vowels = set("aeiouAEIOU")

    def _soundex(self, text: str) -> str:
        """
        Simplified soundex-like encoding.
        """
        if not text:
            return ""

        text = text.upper()
        result = [text[0]]

        # Soundex coding
        coding = {
            "B": "1",
            "F": "1",
            "P": "1",
            "V": "1",
            "C": "2",
            "G": "2",
            "J": "2",
            "K": "2",
            "Q": "2",
            "S": "2",
            "X": "2",
            "Z": "2",
            "D": "3",
            "T": "3",
            "L": "4",
            "M": "5",
            "N": "5",
            "R": "6",
        }

        prev_code = None
        for char in text[1:]:
            code = coding.get(char)
            if code and code != prev_code:
                result.append(code)
                prev_code = code
            if char in self.vowels:
                prev_code = None

        return "".join(result).ljust(4, "0")[:4]

    def _metaphone(self, text: str) -> str:
        """
        Simplified metaphone-like encoding.
        """
        if not text:
            return ""

        text = text.upper()

        # Simple transformations
        rules = [
            ("KN", "N"),
            ("GN", "N"),
            ("PN", "N"),
            ("AE", "E"),
            ("WR", "R"),
            ("WH", "W"),
            ("X", "S"),
            ("PH", "F"),
            ("CI", "SI"),
            ("CE", "SE"),
            ("CY", "SY"),
            ("CK", "K"),
            ("CC", "K"),
        ]

        for pattern, replacement in rules:
            text = text.replace(pattern, replacement)

        return text

    def match(
        self, query: str, candidates: List[str], threshold: float = 0.7
    ) -> List[Tuple[str, float]]:
        """Match based on phonetic similarity."""
        query_soundex = self._soundex(query)
        query_metaphone = self._metaphone(query)

        results = []

        for candidate in candidates:
            candidate_soundex = self._soundex(candidate)
            candidate_metaphone = self._metaphone(candidate)

            # Calculate phonetic similarity
            soundex_score = 1.0 if query_soundex == candidate_soundex else 0.0

            metaphone_score = SequenceMatcher(None, query_metaphone, candidate_metaphone).ratio()

            # Combined score
            score = (soundex_score * 0.3) + (metaphone_score * 0.7)

            if score >= threshold:
                results.append((candidate, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results


class SmartNameResolver:
    """
    Smart name resolution with context awareness.
    """

    def __init__(self) -> None:
        self.fuzzy = FuzzyMatcher(threshold=0.7)
        self.phonetic = PhoneticMatcher()
        self.history: List[str] = []
        self.context_weights: DefaultDict[str, float] = defaultdict(float)

    def add_to_history(self, name: str) -> None:
        """Add successful resolution to history."""
        self.history.append(name)
        if len(self.history) > 100:
            self.history.pop(0)

        # Boost context weight
        self.context_weights[name] += 0.1

    def resolve(
        self,
        query: str,
        candidates: List[str],
        context_hint: Optional[str] = None,
    ) -> Optional[str]:
        """
        Resolve name with context awareness.

        Args:
            query: User input
            candidates: Available names
            context_hint: Optional context type ("object", "material", "action", etc.)
        """
        if not query or not candidates:
            return None

        # Try exact match first
        query_lower = query.lower()
        for candidate in candidates:
            if candidate.lower() == query_lower:
                self.add_to_history(candidate)
                return candidate

        # Try fuzzy matching
        fuzzy_results = self.fuzzy.match(query, candidates, limit=5)

        # Try phonetic matching
        phonetic_results = self.phonetic.match(query, candidates)

        # Combine and score
        combined_scores: Dict[str, float] = defaultdict(float)

        for name, score in fuzzy_results:
            combined_scores[name] += score * 0.7

            # Boost if in history
            if name in self.history:
                combined_scores[name] += 0.1

        for name, score in phonetic_results:
            combined_scores[name] += score * 0.3

        if not combined_scores:
            return None

        # Get best match
        best_name: str = max(combined_scores.keys(), key=lambda k: combined_scores[k])
        best_score = combined_scores[best_name]

        if best_score >= 0.6:
            self.add_to_history(best_name)
            return best_name

        return None

    def suggest(self, query: str, candidates: List[str], top_n: int = 3) -> List[str]:
        """Suggest possible matches."""
        results = self.fuzzy.match(query, candidates, limit=top_n, min_score=0.4)
        return [name for name, _ in results]


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def fuzzy_match(
    query: str, candidates: List[str], threshold: float = 0.6, limit: int = 5
) -> List[Tuple[str, float]]:
    """
    Quick fuzzy match function.

    Example:
        >>> fuzzy_match("cube", ["Cube", "Sphere", "Cylinder"])
        [("Cube", 1.0)]

        >>> fuzzy_match("cyl", ["Cube", "Sphere", "Cylinder"])
        [("Cylinder", 0.95)]
    """
    matcher = FuzzyMatcher(threshold=threshold)
    return matcher.match(query, candidates, limit=limit)


def find_best_match(query: str, candidates: List[str], threshold: float = 0.6) -> Optional[str]:
    """Find single best match."""
    matcher = FuzzyMatcher(threshold=threshold)
    result = matcher.best_match(query, candidates)
    return result[0] if result else None


def resolve_name(query: str, candidates: List[str], use_context: bool = True) -> Optional[str]:
    """
    Resolve name with full intelligence.

    Uses fuzzy matching, phonetic matching, and context awareness.
    """
    resolver = SmartNameResolver()
    return resolver.resolve(query, candidates)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "FuzzyMatcher",
    "MultiFieldMatcher",
    "PhoneticMatcher",
    "SmartNameResolver",
    "fuzzy_match",
    "find_best_match",
    "resolve_name",
]
