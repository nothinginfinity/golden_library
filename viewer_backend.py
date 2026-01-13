#!/usr/bin/env python3
"""
Golden Library - 3D Viewer Backend
Serves handoff data to the 3D visualization
"""

from flask import Flask, jsonify, send_file
from flask_cors import CORS
from pathlib import Path
import json
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from handoff_slim import HandoffCompressor

app = Flask(__name__)
CORS(app)  # Enable CORS for local development

# Initialize compressor
compressor = HandoffCompressor()


@app.route('/')
def index():
    """Serve the 3D viewer"""
    return send_file('viewer.html')


@app.route('/api/handoffs')
def get_handoffs():
    """Get all handoffs with metadata"""
    try:
        result = compressor.list_handoffs()

        if result.get('ok'):
            return jsonify({
                "ok": True,
                "count": result['count'],
                "handoffs": result['handoffs']
            })
        else:
            return jsonify({"ok": False, "error": "Failed to load handoffs"}), 500

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/handoff/<handoff_id>')
def get_handoff(handoff_id):
    """Get detailed stats for a specific handoff"""
    try:
        result = compressor.get_handoff_stats(handoff_id)

        if result.get('ok'):
            return jsonify(result)
        else:
            return jsonify({"ok": False, "error": "Handoff not found"}), 404

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/handoff/<handoff_id>/decompress', methods=['POST'])
def decompress_handoff(handoff_id):
    """Decompress a handoff"""
    try:
        result = compressor.decompress_handoff(handoff_id)

        if result.get('ok'):
            return jsonify(result)
        else:
            return jsonify({"ok": False, "error": result.get('error')}), 500

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/stats')
def get_stats():
    """Get overall compression statistics"""
    try:
        handoffs_result = compressor.list_handoffs()

        if handoffs_result.get('ok'):
            handoffs = handoffs_result['handoffs']

            total_original = sum(h.get('original_size', 0) for h in handoffs)
            total_compressed = sum(h.get('final_size', 0) for h in handoffs)
            avg_reduction = round((1 - total_compressed / total_original) * 100, 1) if total_original > 0 else 0

            return jsonify({
                "ok": True,
                "total_handoffs": len(handoffs),
                "total_original_bytes": total_original,
                "total_compressed_bytes": total_compressed,
                "avg_reduction_percent": avg_reduction,
                "formats": {
                    "slim_only": sum(1 for h in handoffs if h.get('compression_format') == 'slim_only'),
                    "slim_v4z": sum(1 for h in handoffs if h.get('compression_format') == 'slim_v4z'),
                    "slim_fsl": sum(1 for h in handoffs if h.get('compression_format') == 'slim_fsl'),
                    "slim_ztpcf": sum(1 for h in handoffs if h.get('compression_format') == 'slim_ztpcf'),
                }
            })
        else:
            return jsonify({"ok": False, "error": "Failed to load handoffs"}), 500

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Golden Library 3D Viewer Backend")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    print(f"""
🏆 Golden Library 3D Viewer
============================

Backend running at: http://{args.host}:{args.port}
Open in browser:    http://{args.host}:{args.port}

Press Ctrl+C to stop
""")

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
