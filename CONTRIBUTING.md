# Contributing to Golden Library

Thank you for your interest in contributing! 🎉

## Priority Areas

### 1. Bug Fixes (High Priority)
- **SLIM Converter**: Fix nested structure handling in Claude Code JSONL
- **Roundtrip Testing**: Ensure JSONL → SLIM → JSONL is 100% lossless
- See issues tagged with `bug` and `priority-high`

### 2. Compression Integrations
- **V4Z Module**: Integrate token-based compression
- **FSL Module**: Integrate semantic compression
- **ZTPCF Module**: Integrate structured data compression
- Auto-detect best format based on content analysis

### 3. Testing
- Unit tests for SLIM converter edge cases
- Integration tests for handoff system
- Benchmark tests for different conversation types
- Fuzz testing for robustness

### 4. Documentation
- Usage tutorials and examples
- API reference documentation
- Video walkthroughs
- Architecture deep-dives

### 5. UI Development
- Compression settings component
- Terminal library viewer
- QA.Stone browser interface

## Getting Started

1. **Fork the repository**
2. **Clone your fork**:
   ```bash
   git clone https://github.com/yourusername/golden_library.git
   cd golden_library
   ```
3. **Create a branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. **Make your changes**
5. **Test thoroughly**
6. **Submit a pull request**

## Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/

# Run linter
flake8 src/

# Run type checker
mypy src/
```

## Code Style

- Follow PEP 8
- Use type hints
- Write docstrings for all public functions
- Keep functions small and focused
- Comment complex logic

## Testing Requirements

All PRs must include:
- Unit tests for new functionality
- Integration tests if applicable
- Documentation updates
- Updated CHANGELOG.md

## Reporting Issues

When reporting bugs:
- Provide minimal reproducible example
- Include Python version and OS
- Attach sample JSONL file (if possible)
- Describe expected vs actual behavior

## Questions?

- Open a [Discussion](https://github.com/yourusername/golden_library/discussions)
- Join our [Discord](#) (coming soon)
- Email: your.email@example.com

---

**Thank you for making Golden Library better!** 🏆
