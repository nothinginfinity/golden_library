#!/usr/bin/env python3
"""
Test script to validate FAQ capabilities of the Golden Library assistant.
Tests all 4 tools with various query types mentioned in the FAQ.
"""

import json
import requests
import sys
from datetime import datetime

BASE_URL = "http://localhost:8080"

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_test_header(test_name):
    print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.OKCYAN}TEST: {test_name}{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")

def print_success(message):
    print(f"{Colors.OKGREEN}✓ {message}{Colors.ENDC}")

def print_failure(message):
    print(f"{Colors.FAIL}✗ {message}{Colors.ENDC}")

def print_info(message):
    print(f"{Colors.OKBLUE}ℹ {message}{Colors.ENDC}")

def send_chat_message(message, model="claude"):
    """Send a chat message to the assistant and get streaming response."""
    url = f"{BASE_URL}/api/assistant/chat"

    payload = {
        "message": message,
        "history": [],
        "model": model
    }

    try:
        response = requests.post(url, json=payload, stream=True, timeout=30)

        if response.status_code != 200:
            print_failure(f"Server returned status {response.status_code}")
            return None

        full_response = ""
        tool_calls = []

        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data_str = line[6:]
                    try:
                        data = json.loads(data_str)

                        if 'chunk' in data:
                            full_response += data['chunk']

                        if 'tool_call' in data:
                            tool_calls.append(data['tool_call'])

                        if 'error' in data:
                            print_failure(f"Error: {data['error']}")
                            return None

                    except json.JSONDecodeError:
                        pass

        return {
            'response': full_response,
            'tool_calls': tool_calls
        }

    except requests.exceptions.ConnectionError:
        print_failure("Could not connect to dashboard server. Is it running on port 8080?")
        return None
    except Exception as e:
        print_failure(f"Error: {str(e)}")
        return None

def test_search_history():
    """Test search_history tool with various query types from FAQ."""
    print_test_header("Testing search_history Tool")

    test_queries = [
        "Find all conversations about websockets",
        "Search for file edits related to API",
        "Show me plans from last week",
        "debugging sessions in phi_proxy",
        "What did I work on yesterday?",
    ]

    for query in test_queries:
        print_info(f"Query: '{query}'")
        result = send_chat_message(query)

        if result:
            print_success(f"Response received ({len(result['response'])} chars)")
            if result['tool_calls']:
                for tool in result['tool_calls']:
                    print_info(f"  Tool used: {tool['name']}")
                    print_info(f"  Parameters: {json.dumps(tool['input'], indent=4)}")
        else:
            print_failure("No response received")

        print()

def test_get_related_items():
    """Test get_related_items tool."""
    print_test_header("Testing get_related_items Tool")

    # First, get a sample item ID from the index
    try:
        response = requests.get(f"{BASE_URL}/api/unified/list")
        if response.status_code == 200:
            data = response.json()
            if data.get('items') and len(data['items']) > 0:
                sample_item = data['items'][0]
                item_id = sample_item.get('id')
                item_display = sample_item.get('display', 'Unknown')

                print_info(f"Testing with item: {item_display}")
                print_info(f"Item ID: {item_id}")

                query = f"Show me items related to session {item_id}"
                result = send_chat_message(query)

                if result:
                    print_success(f"Response received ({len(result['response'])} chars)")
                    if result['tool_calls']:
                        for tool in result['tool_calls']:
                            print_info(f"  Tool used: {tool['name']}")
                else:
                    print_failure("No response received")
            else:
                print_failure("No items in index to test with")
        else:
            print_failure(f"Could not fetch index (status {response.status_code})")
    except Exception as e:
        print_failure(f"Error: {str(e)}")

def test_get_timeline():
    """Test get_timeline tool."""
    print_test_header("Testing get_timeline Tool")

    test_queries = [
        "Show my activity timeline for this week",
        "Create a monthly breakdown of my sessions",
        "What's my daily activity pattern?",
    ]

    for query in test_queries:
        print_info(f"Query: '{query}'")
        result = send_chat_message(query)

        if result:
            print_success(f"Response received ({len(result['response'])} chars)")
            if result['tool_calls']:
                for tool in result['tool_calls']:
                    print_info(f"  Tool used: {tool['name']}")
                    print_info(f"  Parameters: {json.dumps(tool['input'], indent=4)}")
        else:
            print_failure("No response received")

        print()

def test_create_artifact():
    """Test create_artifact tool."""
    print_test_header("Testing create_artifact Tool")

    test_queries = [
        "Create a checklist of all my incomplete todos",
        "Make a table of projects I've worked on",
        "Show a timeline visualization of my December activity",
    ]

    for query in test_queries:
        print_info(f"Query: '{query}'")
        result = send_chat_message(query)

        if result:
            print_success(f"Response received ({len(result['response'])} chars)")
            if result['tool_calls']:
                for tool in result['tool_calls']:
                    print_info(f"  Tool used: {tool['name']}")
                    print_info(f"  Artifact type: {tool['input'].get('type', 'unknown')}")
        else:
            print_failure("No response received")

        print()

def test_natural_language_understanding():
    """Test natural language query understanding from FAQ examples."""
    print_test_header("Testing Natural Language Understanding")

    faq_queries = [
        "What can you help me with?",
        "What are all your capabilities?",
        "How do I search for old sessions?",
        "Show me examples of what you can do",
        "What types of artifacts can you make?",
    ]

    for query in faq_queries:
        print_info(f"FAQ Query: '{query}'")
        result = send_chat_message(query)

        if result:
            print_success(f"Response received ({len(result['response'])} chars)")
            # Check if response mentions key FAQ elements
            response_lower = result['response'].lower()

            checks = []
            if "search" in response_lower or "history" in response_lower:
                checks.append("mentions search capabilities")
            if "tool" in response_lower or "function" in response_lower:
                checks.append("explains tools")
            if "artifact" in response_lower or "visualization" in response_lower:
                checks.append("describes artifacts")

            if checks:
                print_success(f"  Response quality: {', '.join(checks)}")
        else:
            print_failure("No response received")

        print()

def test_server_health():
    """Check if server is running and responding."""
    print_test_header("Server Health Check")

    try:
        # Check main page
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code == 200:
            print_success("Dashboard server is running")
        else:
            print_failure(f"Dashboard returned status {response.status_code}")
            return False

        # Check API endpoint
        response = requests.get(f"{BASE_URL}/api/stats", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_success(f"API responding - {data.get('total_conversations', 0)} conversations indexed")
        else:
            print_failure(f"API returned status {response.status_code}")
            return False

        # Check unified index
        response = requests.get(f"{BASE_URL}/api/unified/list", timeout=5)
        if response.status_code == 200:
            data = response.json()
            total_items = len(data.get('items', []))
            print_success(f"Unified index loaded - {total_items} total items")

            # Count by type
            items = data.get('items', [])
            types = {}
            for item in items:
                item_type = item.get('type', 'unknown')
                types[item_type] = types.get(item_type, 0) + 1

            print_info("Item breakdown:")
            for item_type, count in sorted(types.items()):
                print_info(f"  - {item_type}: {count}")
        else:
            print_failure(f"Unified index returned status {response.status_code}")
            return False

        return True

    except requests.exceptions.ConnectionError:
        print_failure("Could not connect to server on port 8080")
        print_info("Start server with: python3 ~/ztgi/golden_library/dashboard_server.py")
        return False
    except Exception as e:
        print_failure(f"Error: {str(e)}")
        return False

def main():
    """Run all FAQ capability tests."""
    print(f"\n{Colors.BOLD}Golden Library FAQ Capabilities Test Suite{Colors.ENDC}")
    print(f"Testing dashboard server at {BASE_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Check server health first
    if not test_server_health():
        print_failure("\nServer health check failed. Aborting tests.")
        sys.exit(1)

    # Run capability tests
    test_natural_language_understanding()
    test_search_history()
    test_get_related_items()
    test_get_timeline()
    test_create_artifact()

    # Summary
    print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.OKGREEN}All tests completed!{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")

    print_info("Next steps:")
    print_info("1. Open http://localhost:8080 in your browser")
    print_info("2. Try asking the assistant about its capabilities")
    print_info("3. Test natural language queries interactively")
    print_info("4. Verify tool responses match FAQ documentation")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Tests interrupted by user{Colors.ENDC}")
        sys.exit(0)
