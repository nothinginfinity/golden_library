#!/usr/bin/env python3
"""
Unit Tests for Selective Decompression

Tests the selective decompression features:
- Selective reference resolution
- Section extraction
- Index searching
- Conversation searching
"""

import unittest
import json
import tempfile
import shutil
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from index_extractor import IndexExtractor
from index_searcher import IndexSearcher
from conversation_searcher import ConversationSearcher
from search_result import SearchMatch, SearchResult, IndexMatch


class TestSelectiveResolution(unittest.TestCase):
    """Test selective reference resolution."""

    def setUp(self):
        """Set up test fixtures."""
        self.extractor = IndexExtractor()
        self.temp_dir = tempfile.mkdtemp()
        self.index_dir = Path(self.temp_dir) / "indexes"
        self.index_dir.mkdir(parents=True)

        # Create test indexes
        self._create_test_indexes()

    def tearDown(self):
        """Clean up test files."""
        shutil.rmtree(self.temp_dir)

    def _create_test_indexes(self):
        """Create test index files."""
        # Cold index
        cold_index = {
            "version": "1.0",
            "tier": "cold",
            "tier_id": "global",
            "patterns": {
                "$cold#abc123": {
                    "content": {"type": "system", "message": "authentication system initialized"},
                    "category": "system_message",
                    "occurrences": 5,
                    "size_bytes": 100
                },
                "$cold#def456": {
                    "content": {"type": "tool", "name": "search", "description": "search tool"},
                    "category": "tool_definition",
                    "occurrences": 3,
                    "size_bytes": 80
                }
            }
        }

        cold_path = self.index_dir / "global_cold.json"
        with open(cold_path, 'w') as f:
            json.dump(cold_index, f)

        # Warm index
        warm_index = {
            "version": "1.0",
            "tier": "warm",
            "tier_id": "test_project",
            "patterns": {
                "$warm#xyz789": {
                    "content": {"data": "important project data"},
                    "category": "project_data",
                    "occurrences": 4,
                    "size_bytes": 60
                }
            }
        }

        warm_dir = self.index_dir / "projects"
        warm_dir.mkdir(parents=True)
        warm_path = warm_dir / "test_project_warm.json"
        with open(warm_path, 'w') as f:
            json.dump(warm_index, f)

    def test_resolve_selective_single_ref(self):
        """Test resolving a single $ref."""
        compressed = '''
Line 1: Some content
Line 2: "$cold#abc123"
Line 3: More content
Line 4: "$cold#def456"
        '''.strip()

        # Resolve only first ref
        result = self.extractor.resolve_references_selective(
            compressed,
            ["$cold#abc123"],
            ["cold"],
            str(self.index_dir)
        )

        # First ref should be resolved
        self.assertIn('authentication system', result)
        self.assertNotIn('"$cold#abc123"', result)

        # Second ref should remain
        self.assertIn('"$cold#def456"', result)

    def test_resolve_selective_multiple_refs(self):
        """Test resolving multiple specific $refs."""
        compressed = '''
Line 1: "$cold#abc123"
Line 2: "$cold#def456"
Line 3: "$warm#xyz789"
        '''.strip()

        # Resolve cold refs only
        result = self.extractor.resolve_references_selective(
            compressed,
            ["$cold#abc123", "$cold#def456"],
            ["cold"],
            str(self.index_dir)
        )

        # Cold refs should be resolved
        self.assertIn('authentication system', result)
        self.assertIn('search tool', result)

        # Warm ref should remain
        self.assertIn('"$warm#xyz789"', result)

    def test_resolve_selective_nonexistent_ref(self):
        """Test resolving with non-existent ref ID."""
        compressed = 'Line 1: "$cold#abc123"'

        # Try to resolve a ref that doesn't exist
        result = self.extractor.resolve_references_selective(
            compressed,
            ["$cold#nonexistent"],
            ["cold"],
            str(self.index_dir)
        )

        # Original ref should remain unchanged
        self.assertEqual(compressed, result)


class TestSectionExtraction(unittest.TestCase):
    """Test section extraction from compressed content."""

    def setUp(self):
        """Set up test fixtures."""
        self.extractor = IndexExtractor()
        self.content = '\n'.join([f"Line {i}" for i in range(100)])

    def test_get_section_basic(self):
        """Test extracting a basic section."""
        result = self.extractor.get_section(
            self.content,
            10,
            20,
            resolve_refs=False
        )

        lines = result.split('\n')
        self.assertEqual(len(lines), 10)
        self.assertEqual(lines[0], "Line 10")
        self.assertEqual(lines[-1], "Line 19")

    def test_get_section_boundaries(self):
        """Test section extraction at boundaries."""
        # Start of file
        result = self.extractor.get_section(self.content, 0, 5, resolve_refs=False)
        self.assertTrue(result.startswith("Line 0"))

        # End of file
        result = self.extractor.get_section(self.content, 95, 200, resolve_refs=False)
        lines = result.split('\n')
        self.assertEqual(lines[-1], "Line 99")

    def test_get_section_negative_indices(self):
        """Test handling of negative indices."""
        result = self.extractor.get_section(self.content, -5, 10, resolve_refs=False)
        # Should start from 0
        self.assertTrue(result.startswith("Line 0"))


class TestIndexSearcher(unittest.TestCase):
    """Test index searching functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.index_dir = Path(self.temp_dir) / "indexes"
        self.index_dir.mkdir(parents=True)

        # Create test index
        self._create_test_index()

        self.searcher = IndexSearcher(str(self.index_dir))

    def tearDown(self):
        """Clean up test files."""
        shutil.rmtree(self.temp_dir)

    def _create_test_index(self):
        """Create test index file."""
        index = {
            "version": "1.0",
            "tier": "cold",
            "tier_id": "global",
            "patterns": {
                "$cold#auth001": {
                    "content": "authentication module for user login",
                    "category": "system",
                    "occurrences": 5,
                    "size_bytes": 100
                },
                "$cold#search001": {
                    "content": "search functionality with filters",
                    "category": "feature",
                    "occurrences": 3,
                    "size_bytes": 80
                }
            }
        }

        cold_path = self.index_dir / "global_cold.json"
        with open(cold_path, 'w') as f:
            json.dump(index, f)

    def test_search_indexes_finds_match(self):
        """Test searching indexes for a term."""
        matches = self.searcher.search_indexes(
            "authentication",
            ["cold"]
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].ref_id, "$cold#auth001")
        self.assertIn("authentication", matches[0].content_preview)

    def test_search_indexes_case_insensitive(self):
        """Test case-insensitive search."""
        matches = self.searcher.search_indexes(
            "AUTHENTICATION",
            ["cold"],
            case_sensitive=False
        )

        self.assertEqual(len(matches), 1)

    def test_search_indexes_no_match(self):
        """Test search with no matches."""
        matches = self.searcher.search_indexes(
            "nonexistent",
            ["cold"]
        )

        self.assertEqual(len(matches), 0)

    def test_find_refs_in_content(self):
        """Test finding ref locations in content."""
        content = '''
Line 0: Some text
Line 1: "$cold#auth001"
Line 2: More text
Line 3: "$cold#auth001" appears again
Line 4: "$cold#search001"
        '''.strip()

        locations = self.searcher.find_refs_in_content(
            content,
            ["$cold#auth001", "$cold#search001"]
        )

        self.assertIn("$cold#auth001", locations)
        self.assertIn("$cold#search001", locations)
        self.assertEqual(len(locations["$cold#auth001"]), 2)
        self.assertEqual(locations["$cold#auth001"], [1, 3])
        self.assertEqual(locations["$cold#search001"], [4])

    def test_get_available_indexes(self):
        """Test getting list of available indexes."""
        available = self.searcher.get_available_indexes()

        self.assertIn("cold", available)
        self.assertEqual(len(available["cold"]), 1)


class TestConversationSearcher(unittest.TestCase):
    """Test conversation searching functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.index_dir = Path(self.temp_dir) / "indexes"
        self.index_dir.mkdir(parents=True)

        # Create test files
        self._create_test_files()

        self.searcher = ConversationSearcher(str(self.index_dir))

    def tearDown(self):
        """Clean up test files."""
        shutil.rmtree(self.temp_dir)

    def _create_test_files(self):
        """Create test compressed files and indexes."""
        # Create index
        index = {
            "version": "1.0",
            "tier": "cold",
            "tier_id": "global",
            "patterns": {
                "$cold#error001": {
                    "content": "error handling system",
                    "category": "system",
                    "occurrences": 3,
                    "size_bytes": 60
                }
            }
        }

        cold_path = self.index_dir / "global_cold.json"
        with open(cold_path, 'w') as f:
            json.dump(index, f)

        # Create compressed file
        self.test_file = Path(self.temp_dir) / "test.slim.indexed"
        content = '''
Line 0: User asked about authentication
Line 1: "$cold#error001"
Line 2: System responded with help
Line 3: Another error mention
Line 4: Final response
        '''.strip()

        with open(self.test_file, 'w') as f:
            f.write(content)

    def test_search_finds_text_match(self):
        """Test searching finds direct text matches."""
        result = self.searcher.search(
            "authentication",
            [str(self.test_file)],
            preview_context=1
        )

        self.assertGreater(result.total_matches, 0)
        self.assertTrue(any("authentication" in m.match_text for m in result.matches))

    def test_search_directory(self):
        """Test searching a directory."""
        result = self.searcher.search_directory(
            "error",
            str(self.temp_dir),
            pattern="*.slim.indexed",
            preview_context=2
        )

        self.assertGreater(result.total_matches, 0)
        self.assertEqual(result.files_searched, 1)

    def test_preview_file(self):
        """Test previewing a file."""
        preview = self.searcher.preview_file(
            str(self.test_file),
            start_line=0,
            num_lines=3,
            resolve_refs=False
        )

        lines = preview.split('\n')
        self.assertEqual(len(lines), 3)
        self.assertIn("authentication", lines[0])


class TestSearchResult(unittest.TestCase):
    """Test SearchResult dataclass functionality."""

    def test_tokens_saved_calculation(self):
        """Test tokens saved calculation."""
        result = SearchResult(
            query="test",
            total_matches=5,
            files_searched=2,
            tokens_used=1000,
            full_decompress_tokens=10000
        )

        self.assertEqual(result.tokens_saved, 9000)
        self.assertEqual(result.savings_percent, 90.0)

    def test_savings_percent_with_zero(self):
        """Test savings percent with zero full_decompress."""
        result = SearchResult(
            query="test",
            total_matches=0,
            files_searched=1,
            tokens_used=100
        )

        self.assertEqual(result.savings_percent, 0.0)


class TestIntegration(unittest.TestCase):
    """Integration tests for complete workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.index_dir = Path(self.temp_dir) / "indexes"
        self.index_dir.mkdir(parents=True)

        self.extractor = IndexExtractor()
        self.searcher = ConversationSearcher(str(self.index_dir))

    def tearDown(self):
        """Clean up test files."""
        shutil.rmtree(self.temp_dir)

    def test_full_workflow(self):
        """Test complete compress -> search -> expand workflow."""
        # 1. Create original content
        original_content = json.dumps({
            "messages": [
                {"role": "user", "content": "Tell me about authentication"},
                {"role": "assistant", "content": "Authentication is important"},
                {"role": "user", "content": "What about authorization?"},
                {"role": "assistant", "content": "Authorization controls access"}
            ]
        }, indent=2)

        # 2. Compress with index extraction
        result = self.extractor.extract_patterns(
            original_content,
            threshold=1,  # Low threshold for test
            output_dir=str(self.index_dir),
            session_id="test_session",
            project_id="test_project"
        )

        # 3. Save compressed content
        compressed_file = Path(self.temp_dir) / "test.slim.indexed"
        with open(compressed_file, 'w') as f:
            f.write(result.content_with_refs)

        # 4. Search compressed content
        search_result = self.searcher.search(
            "authentication",
            [str(compressed_file)],
            preview_context=2,
            auto_expand=False
        )

        # 5. Verify search found matches
        self.assertGreater(search_result.total_matches, 0)

        # 6. Verify token savings
        if search_result.full_decompress_tokens:
            self.assertLess(
                search_result.tokens_used,
                search_result.full_decompress_tokens
            )


def run_tests():
    """Run all tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestSelectiveResolution))
    suite.addTests(loader.loadTestsFromTestCase(TestSectionExtraction))
    suite.addTests(loader.loadTestsFromTestCase(TestIndexSearcher))
    suite.addTests(loader.loadTestsFromTestCase(TestConversationSearcher))
    suite.addTests(loader.loadTestsFromTestCase(TestSearchResult))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
