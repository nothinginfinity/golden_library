# Changelog

All notable changes to Golden Library will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- SLIM format specification (schema-once compression)
- `slim_converter.py` - JSONL ↔ SLIM conversion
- `handoff_slim.py` - Handoff compression system
- CLI interfaces for compression/decompression
- Comprehensive documentation and roadmap
- Examples and usage guides

### Known Issues
- SLIM converter fails on complex nested structures
- Roundtrip testing not 100% lossless yet
- V4Z/FSL/ZTPCF integration placeholders only

## [0.1.0] - 2026-01-13

### Added
- Initial release
- Core SLIM compression framework
- Handoff system architecture
- MIT license
- Contributing guidelines

[Unreleased]: https://github.com/nothinginfinity/golden_library/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/nothinginfinity/golden_library/releases/tag/v0.1.0
