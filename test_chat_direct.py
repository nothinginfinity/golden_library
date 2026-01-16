#!/usr/bin/env python3
"""Direct test of the chat endpoint to debug why it's not responding."""

import requests
import json
import time

BASE_URL = "http://localhost:8080"

print("Testing chat endpoint directly...")
print(f"URL: {BASE_URL}/api/assistant/chat")
print()

# Test data
payload = {
    "message": "What can you help me with?",
    "history": [],
    "model": "claude"
}

print("Sending request...")
print(f"Payload: {json.dumps(payload, indent=2)}")
print()

try:
    response = requests.post(
        f"{BASE_URL}/api/assistant/chat",
        json=payload,
        stream=True,
        timeout=30
    )

    print(f"Status: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    print()

    if response.status_code != 200:
        print(f"Error: Server returned {response.status_code}")
        print(response.text)
    else:
        print("Response stream:")
        print("-" * 80)

        chunk_count = 0
        start_time = time.time()

        for line in response.iter_lines():
            if line:
                chunk_count += 1
                elapsed = time.time() - start_time

                line = line.decode('utf-8')
                print(f"[{elapsed:.2f}s] {line}")

                # Parse SSE data
                if line.startswith('data: '):
                    data_str = line[6:]
                    try:
                        data = json.loads(data_str)

                        if 'error' in data:
                            print(f"  ERROR: {data['error']}")
                            break
                        elif 'chunk' in data:
                            print(f"  TEXT: {data['chunk'][:50]}...")
                        elif 'tool_call' in data:
                            print(f"  TOOL: {data['tool_call']}")
                        elif 'done' in data:
                            print(f"  DONE")
                            break
                    except json.JSONDecodeError as e:
                        print(f"  JSON parse error: {e}")

        print("-" * 80)
        print(f"\nReceived {chunk_count} chunks in {time.time() - start_time:.2f}s")

        if chunk_count == 0:
            print("\n⚠️  WARNING: No chunks received! Stream was empty.")

except requests.exceptions.Timeout:
    print("ERROR: Request timed out after 30 seconds")
except requests.exceptions.ConnectionError as e:
    print(f"ERROR: Could not connect to server: {e}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
