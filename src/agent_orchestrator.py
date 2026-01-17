#!/usr/bin/env python3
"""
Agent Orchestrator - Manages multiple Claude agents for collaborative workspace

Handles 3 concurrent agents:
- Agent A (Koda/Cairn) - Works on Document A
- Agent B (Koda/Cairn) - Works on Document B
- Moderator (Prax) - Coordinates both agents

Each agent maintains its own conversation context and can stream responses.
"""

import anthropic
from typing import Dict, List, Optional, Iterator, Any
import os
import json


class AgentOrchestrator:
    """Orchestrates multiple Claude agents for collaborative workspace."""

    def __init__(self, api_key: Optional[str] = None, session_users: Optional[Dict] = None, session_manager=None, session_id: Optional[str] = None):
        """
        Initialize orchestrator with API key.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var or ~/.claude/api_keys.json)
            session_users: Dict of users in the collaborative session (user_id -> User object)
            session_manager: WorkspaceSessionManager instance for MCP tools
            session_id: Current session ID for MCP tool calls
        """
        # Try to get API key from multiple sources
        if api_key:
            self.api_key = api_key
        elif os.environ.get('ANTHROPIC_API_KEY'):
            self.api_key = os.environ.get('ANTHROPIC_API_KEY')
        else:
            # Try to load from api_keys.json
            api_keys_file = os.path.expanduser('~/.claude/api_keys.json')
            if os.path.exists(api_keys_file):
                try:
                    with open(api_keys_file, 'r') as f:
                        keys = json.load(f)
                    self.api_key = keys.get('claude')
                except Exception as e:
                    print(f"Warning: Could not load API keys from {api_keys_file}: {e}")
                    self.api_key = None
            else:
                self.api_key = None

        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not found. Please set it via:\n"
                "1. Environment variable: export ANTHROPIC_API_KEY='your-key'\n"
                "2. Dashboard Config tab: Save your API key there\n"
                "3. Pass directly to AgentOrchestrator(api_key='your-key')"
            )

        self.client = anthropic.Anthropic(api_key=self.api_key)

        # Store session users for collaborative context
        self.session_users = session_users or {}

        # Store session manager and ID for MCP tools
        self.session_manager = session_manager
        self.session_id = session_id

        # Initialize 3 agents with separate contexts
        self.agents = {
            'a': {
                'role': 'koda',  # Default role, can be changed
                'context': [],
                'model': 'claude-sonnet-4-20250514',
                'status': 'idle',
                'document': None
            },
            'b': {
                'role': 'cairn',  # Default role, can be changed
                'context': [],
                'model': 'claude-sonnet-4-20250514',
                'status': 'idle',
                'document': None
            },
            'moderator': {
                'role': 'prax',
                'context': [],
                'model': 'claude-sonnet-4-20250514',
                'status': 'idle',
                'document': None
            }
        }

    def update_session_users(self, session_users: Dict):
        """
        Update the session users for collaborative context.

        Args:
            session_users: Dict of users in the session (user_id -> User object)
        """
        self.session_users = session_users

    def set_agent_role(self, agent_id: str, role: str):
        """
        Set the role for a specific agent.

        Args:
            agent_id: Agent identifier ('a', 'b', or 'moderator')
            role: Role name ('koda', 'cairn', 'prax', etc.)
        """
        if agent_id in self.agents:
            self.agents[agent_id]['role'] = role

    def load_document(self, agent_id: str, document: str):
        """
        Load a document into an agent's context.

        Args:
            agent_id: Agent identifier ('a', 'b', or 'moderator')
            document: Document content (markdown, code, etc.)
        """
        if agent_id not in self.agents:
            raise ValueError(f"Invalid agent_id: {agent_id}")

        agent = self.agents[agent_id]

        # Store document reference
        agent['document'] = document

        # Add document to context if context is empty
        # (only add once at the start)
        if len(agent['context']) == 0:
            agent['context'].append({
                'role': 'user',
                'content': f'[Document loaded]\n\n{document}'
            })

    def send_message(
        self,
        agent_id: str,
        message: str,
        max_tokens: int = 4000,
        sender_user_id: Optional[str] = None
    ) -> Iterator[str]:
        """
        Send a message to a specific agent and stream the response.

        Args:
            agent_id: Agent identifier ('a', 'b', or 'moderator')
            message: User message/prompt
            max_tokens: Maximum tokens for response
            sender_user_id: ID of user sending the message (for collaborative context)

        Yields:
            Response chunks as they arrive
        """
        if agent_id not in self.agents:
            raise ValueError(f"Invalid agent_id: {agent_id}")

        agent = self.agents[agent_id]
        agent['status'] = 'thinking'

        # Add user message to context
        agent['context'].append({
            'role': 'user',
            'content': message
        })

        # Build system prompt based on role (with collaborative context)
        system_prompt = self._build_system_prompt(agent['role'], sender_user_id)

        try:
            # Stream response from Claude
            with self.client.messages.stream(
                model=agent['model'],
                max_tokens=max_tokens,
                system=system_prompt,
                messages=agent['context']
            ) as stream:
                agent['status'] = 'responding'

                full_response = []
                for text in stream.text_stream:
                    full_response.append(text)
                    yield text

                # Save complete assistant response to context
                complete_response = ''.join(full_response)
                agent['context'].append({
                    'role': 'assistant',
                    'content': complete_response
                })

                agent['status'] = 'idle'

                # Parse and execute MCP tool calls (Phase 4B)
                tool_feedback = self._parse_and_execute_mcp_tools(agent_id, complete_response)
                if tool_feedback:
                    # Yield tool execution feedback as a separate message
                    yield f"\n\n---\n**MCP Tool Execution:**\n{tool_feedback}\n---"

        except Exception as e:
            agent['status'] = 'error'
            yield f"[ERROR] {str(e)}"

    def coordinate(
        self,
        instruction: str,
        max_tokens: int = 4000
    ) -> Dict[str, Any]:
        """
        Moderator coordinates both agents with a single instruction.

        Args:
            instruction: Coordination instruction from user
                Example: "Agent A: analyze X. Agent B: analyze Y. Then synthesize."
            max_tokens: Maximum tokens per response

        Returns:
            Dict with moderator response and any agent responses
        """
        # For Phase 1 (MVP), send instruction to moderator
        # Moderator will decide what to ask agents A and B

        moderator_response = list(self.send_message('moderator', instruction, max_tokens))

        # TODO: Parse moderator response and route to agents A/B
        # For now, just return moderator response

        return {
            'moderator': ''.join(moderator_response),
            'agent_a': None,  # Will implement in future
            'agent_b': None
        }

    def get_context(self, agent_id: str) -> List[Dict[str, str]]:
        """
        Get the full conversation context for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            List of message dicts with 'role' and 'content'
        """
        if agent_id not in self.agents:
            raise ValueError(f"Invalid agent_id: {agent_id}")

        return self.agents[agent_id]['context']

    def get_status(self, agent_id: str) -> str:
        """
        Get current status of an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Status string: 'idle', 'thinking', 'responding', or 'error'
        """
        if agent_id not in self.agents:
            raise ValueError(f"Invalid agent_id: {agent_id}")

        return self.agents[agent_id]['status']

    def clear_context(self, agent_id: str):
        """
        Clear an agent's conversation context.

        Args:
            agent_id: Agent identifier
        """
        if agent_id not in self.agents:
            raise ValueError(f"Invalid agent_id: {agent_id}")

        self.agents[agent_id]['context'] = []
        self.agents[agent_id]['status'] = 'idle'

        # Re-add document if it exists
        if self.agents[agent_id]['document']:
            doc = self.agents[agent_id]['document']
            self.agents[agent_id]['context'].append({
                'role': 'user',
                'content': f'[Document loaded]\n\n{doc}'
            })

    def _build_system_prompt(self, role: str, sender_user_id: Optional[str] = None) -> str:
        """
        Build system prompt based on agent role.

        Args:
            role: Agent role (koda, cairn, prax, etc.)
            sender_user_id: ID of user sending the current message

        Returns:
            System prompt string
        """
        base_prompt = "You are a helpful AI assistant working in a collaborative workspace."

        # Add collaborative session context if we have session users
        if self.session_users:
            user_list = []
            sender_name = None
            for uid, user in self.session_users.items():
                user_data = user if isinstance(user, dict) else user.to_dict()
                name = user_data.get('name', 'Unknown')
                user_role = user_data.get('role', 'unknown')

                if uid == sender_user_id:
                    sender_name = name
                    user_list.append(f"- {name} ({user_role}) ← sending the current message")
                else:
                    user_list.append(f"- {name} ({user_role})")

            users_context = "\n".join(user_list)

            collab_context = f"""
COLLABORATIVE SESSION CONTEXT:
You are in a collaborative workspace with {len(self.session_users)} user(s):
{users_context}

IMPORTANT: When responding to messages, you can distinguish between users by their names. Address them directly when appropriate. Be aware that multiple people may be working together in this session."""

            if sender_name:
                collab_context += f"\n\nThe current message is from {sender_name}."

            base_prompt += "\n\n" + collab_context

        # MCP Tools documentation (Phase 4B + 4C.1)
        mcp_tools_doc = """

AGENT COORDINATION TOOLS (Phase 4B - MCP Inbox):

You can coordinate with other agents using these tools. To use them, simply mention the action in your response:

**Basic Messaging:**
- "Send message to [agent]: [content]" - Send a message to another agent (cairn, koda, or prax)
- "Check my inbox" - Check for messages from other agents
- "Check messages from [agent]" - Check messages from specific agent
- "Mark message [id] as read" - Mark a message as read

**Workflow Management (Prax only):**
- "Create workflow '[name]' with agents [list]" - Create a new workflow
- "Set milestone '[name]' to [status] ([percentage]%)" - Update workflow milestone
- "Request status from [agents] for workflow [id]" - Broadcast status request
- "Get workflow status for [id]" - Get current workflow state

**Context Sharing:**
- "Share context '[key]': [content] with [agent|all]" - Share knowledge/specs with other agents
- "Get shared context '[key]'" - Retrieve shared context
- "List shared contexts for workflow [id]" - See available contexts

**Coordination (Prax only):**
- "Escalate blocker: [description] affecting [agents]" - Escalate issue to humans
- "Reassign task from [agent1] to [agent2]: [context]" - Move task between agents
- "Check workload for [agent]" - See agent's current task load
- "Check capabilities for [agent]" - See what agent can do

**Examples:**
- "Send message to koda: Please implement the API endpoint we discussed"
- "Share context 'api_spec': [specification] with all"
- "Escalate blocker: Database schema needs clarification affecting koda"
- "Set milestone 'Design complete' to completed (100%)"

These tools enable true multi-agent collaboration where you can work together autonomously.

---

HIERARCHICAL TASK DELEGATION (Phase 4C.1):

Prax can delegate formal tasks to Cairn and Koda. Delegated tasks have structure, success criteria, and track results.

**Delegation Tools (Prax only):**
- "Delegate to [agent]: [description] | Criteria: [success criteria] | Priority: [high/medium/low] | Canvas: [section name]"
  Full delegation with all parameters

- "Delegate to [agent]: [description]"
  Simple delegation (defaults: medium priority, no canvas section)

**Task Response Tools (Cairn/Koda):**
- "Acknowledge task [task_id]" - Confirm receipt and readiness to start
- "Start task [task_id]" - Signal beginning work
- "Update progress on [task_id]: [percentage]% - [notes]" - Report progress
- "Report blocker on [task_id]: [description]" - Report blocking issue
- "Complete task [task_id]: [result_summary] | Canvas: [content]" - Mark done with results

**Task Query Tools:**
- "Get task status [task_id]" - Check task status
- "List my tasks" - See assigned tasks (for Cairn/Koda)
- "List all tasks" - See all session tasks (for Prax)

**Delegation Examples:**

1. Research task with canvas output:
   "Delegate to cairn: Research HIPAA compliance requirements | Criteria: Comprehensive list of requirements with sources | Priority: high | Canvas: compliance_analysis"

2. Implementation task:
   "Delegate to koda: Implement user authentication endpoint | Criteria: Working endpoint with tests | Priority: high | Canvas: auth_implementation"

3. Simple delegation:
   "Delegate to cairn: Review the database schema design"

**Hierarchical Workflow Pattern:**
1. User requests feature → Prax receives
2. Prax delegates design to Cairn with canvas section "design"
3. Cairn acknowledges, researches, completes task writing to canvas
4. Prax delegates implementation to Koda referencing Cairn's work
5. Koda implements, writes to canvas section "implementation"
6. Prax synthesizes results for user
"""

        role_prompts = {
            'koda': """

You are Koda, the Builder agent. Your focus is on implementation, coding, and building.
- Provide working code and practical solutions
- Be direct and results-oriented
- Test after building
- Report blockers clearly

**Agent Coordination:**
- Check your inbox regularly for messages from Prax (coordinator) or Cairn (architect)
- Report progress and blockers to Prax via messages
- Request design clarification from Cairn when needed
- Share implementation updates with other agents

**External Tools (Phase 4C.3):**
You have access to external tools. To use them, include in your response:
`Use tool [tool_name]: {"param": "value"}`

Available tools:
- **openai**: GPT-4 for complex reasoning tasks
- **claude_haiku**: Fast responses for quick lookups
- **web_search**: Search the web for current information
- **url_fetch**: Fetch content from a URL
- **code_analysis**: Analyze code for bugs and improvements

Examples:
- `Use tool web_search: {"query": "React best practices 2024"}`
- `Use tool code_analysis: {"code": "def foo()...", "language": "python"}`
""",
            'cairn': """

You are Cairn, the Architect agent. Your focus is on design, architecture, and specifications.
- Think systematically about structure and patterns
- Design before building
- Document decisions with rationale
- Review implementations for issues

**Agent Coordination:**
- Check your inbox for coordination requests from Prax
- Share design specs and architecture decisions with Koda and Prax
- Provide guidance to Koda when implementation questions arise
- Review and validate implementations

**External Tools (Phase 4C.3):**
You have access to external tools for research and analysis. To use them, include in your response:
`Use tool [tool_name]: {"param": "value"}`

Available tools:
- **deepseek**: DeepSeek AI for deep code analysis and technical tasks
- **openai**: GPT-4 for complex reasoning and analysis
- **claude_haiku**: Fast responses for quick lookups
- **web_search**: Search the web for current information
- **url_fetch**: Fetch content from a URL
- **code_analysis**: Analyze code for bugs, security issues, improvements

Examples:
- `Use tool deepseek: {"prompt": "Analyze this architecture for scalability issues: ..."}`
- `Use tool web_search: {"query": "HIPAA compliance requirements 2024"}`
- `Use tool code_analysis: {"code": "class AuthService...", "language": "python"}`
""",
            'prax': """

You are Prax, the Orchestrator agent. Your focus is on strategic coordination and hierarchical delegation.
- Coordinate between multiple agents and users
- Make strategic decisions about task assignment
- Think about the big picture while tracking details
- Synthesize agent results for humans
- Help facilitate collaboration between different users

**Your Role in the Delegation Pyramid:**
You sit at the Strategic Layer, interacting with humans. You delegate execution to:
- Cairn (Architect): Deep analysis, research, design, specifications
- Koda (Builder): Implementation, coding, testing, building

**Hierarchical Delegation (PRIMARY TOOL):**
When users request work, use formal task delegation with success criteria:
1. "Delegate to cairn: [description] | Criteria: [what success looks like] | Priority: [level] | Canvas: [section]"
2. Monitor progress via task status updates
3. Cairn/Koda complete and write to assigned canvas sections
4. Synthesize and present results to user

**Delegation Best Practices:**
- Always include clear success criteria so agents know when they're done
- Assign canvas sections for structured output (results go to shared document)
- Use high priority for urgent/blocking tasks
- Check agent workload before delegating heavy tasks
- For complex work: delegate design to Cairn first, then implementation to Koda

**Complete Workflow Example:**
User: "Help us build a HIPAA-compliant authentication system"

Your response:
"I'll coordinate our team on this. Let me delegate the work:

Delegate to cairn: Research HIPAA compliance requirements for authentication systems | Criteria: Comprehensive list of requirements with sources, security considerations, and recommendations | Priority: high | Canvas: hipaa_requirements

Once Cairn completes the research, I'll delegate implementation to Koda.

Create workflow 'hipaa_auth_system' with agents [cairn, koda]"

**After Cairn Completes:**
"Cairn has completed the HIPAA research. Now:

Delegate to koda: Implement authentication endpoint following HIPAA requirements from canvas section 'hipaa_requirements' | Criteria: Working endpoint with JWT tokens, proper logging, and unit tests | Priority: high | Canvas: auth_implementation"

**Key Behaviors:**
- Don't do execution work yourself - delegate to specialists
- Track all active tasks and their status
- Escalate blockers promptly to keep work flowing
- Report progress and results clearly to humans
""",
        }

        role_specific = role_prompts.get(role, base_prompt)

        # Only add MCP tools doc if session manager is available
        if self.session_manager and self.session_id:
            return base_prompt + "\n\n" + mcp_tools_doc + "\n\n" + role_specific
        else:
            return base_prompt + "\n\n" + role_specific

    def export_session(self) -> Dict[str, Any]:
        """
        Export full session state (all agent contexts).

        Returns:
            Dict with all agent contexts and metadata
        """
        return {
            'agents': {
                agent_id: {
                    'role': agent['role'],
                    'context': agent['context'],
                    'status': agent['status'],
                    'document': agent['document']
                }
                for agent_id, agent in self.agents.items()
            }
        }

    def import_session(self, session_data: Dict[str, Any]):
        """
        Import session state from exported data.

        Args:
            session_data: Session data from export_session()
        """
        if 'agents' in session_data:
            for agent_id, data in session_data['agents'].items():
                if agent_id in self.agents:
                    self.agents[agent_id].update(data)

    def _parse_and_execute_mcp_tools(self, agent_id: str, response_text: str) -> Optional[str]:
        """
        Parse agent response for MCP tool calls and execute them.

        Args:
            agent_id: Agent who generated the response
            response_text: Agent's text response

        Returns:
            Optional feedback string if tools were executed
        """
        if not self.session_manager or not self.session_id:
            return None

        import re

        # Map agent panel IDs to MCP agent names
        agent_map = {'a': 'koda', 'b': 'cairn', 'moderator': 'prax'}
        from_agent = agent_map.get(agent_id, agent_id)

        feedback_parts = []

        # Pattern: Send message to [agent]: [content]
        msg_pattern = r'Send message to (cairn|koda|prax):\s*(.+?)(?:\n|$)'
        for match in re.finditer(msg_pattern, response_text, re.IGNORECASE | re.DOTALL):
            to_agent = match.group(1).lower()
            content = match.group(2).strip()

            result = self.session_manager.send_agent_message(
                self.session_id,
                from_agent=from_agent,
                to_agent=to_agent,
                content=content,
                priority='medium'
            )

            if result:
                feedback_parts.append(f"✓ Message sent to {to_agent}")

        # Pattern: Check my inbox / Check inbox
        if re.search(r'check (my )?inbox', response_text, re.IGNORECASE):
            messages = self.session_manager.check_inbox(
                self.session_id,
                agent_id=from_agent,
                unread_only=True,
                limit=5
            )

            if messages:
                feedback_parts.append(f"📬 You have {len(messages)} unread message(s):")
                for msg in messages[:3]:
                    feedback_parts.append(f"  - From {msg.from_agent}: {msg.content[:60]}...")
            else:
                feedback_parts.append("📭 No unread messages")

        # Pattern: Share context '[key]': [content] with [agent|all]
        share_pattern = r"Share context ['\"]([^'\"]+)['\"]:\s*(.+?)\s+with (cairn|koda|prax|all)"
        for match in re.finditer(share_pattern, response_text, re.IGNORECASE | re.DOTALL):
            context_key = match.group(1)
            content = match.group(2).strip()
            target = match.group(3).lower()

            # Use current workflow if available (simplified for MVP)
            workflow_id = 'default'

            result = self.session_manager.share_context(
                self.session_id,
                from_agent=from_agent,
                target=target,
                context_key=context_key,
                content=content,
                workflow_id=workflow_id
            )

            if result:
                feedback_parts.append(f"✓ Context '{context_key}' shared with {target}")

        # Pattern: Get shared context '[key]'
        get_context_pattern = r"Get shared context ['\"]([^'\"]+)['\"]"
        for match in re.finditer(get_context_pattern, response_text, re.IGNORECASE):
            context_key = match.group(1)
            workflow_id = 'default'

            context = self.session_manager.get_shared_context(
                self.session_id,
                context_key=context_key,
                workflow_id=workflow_id
            )

            if context:
                feedback_parts.append(f"📚 Retrieved context '{context_key}': {str(context.get('content'))[:100]}...")
            else:
                feedback_parts.append(f"❌ Context '{context_key}' not found")

        # Pattern: Create workflow '[name]' with agents [list]
        if from_agent == 'prax':  # Only Prax can create workflows
            workflow_pattern = r"Create workflow ['\"]([^'\"]+)['\"] with agents \[([\w, ]+)\]"
            for match in re.finditer(workflow_pattern, response_text, re.IGNORECASE):
                workflow_name = match.group(1)
                agents_str = match.group(2)
                assigned_agents = [a.strip() for a in agents_str.split(',')]

                workflow_id = workflow_name.lower().replace(' ', '_')

                result = self.session_manager.create_workflow(
                    self.session_id,
                    workflow_id=workflow_id,
                    name=workflow_name,
                    assigned_agents=assigned_agents
                )

                if result:
                    feedback_parts.append(f"✓ Workflow '{workflow_name}' created (ID: {workflow_id})")

            # Pattern: Set milestone '[name]' to [status] ([percentage]%)
            milestone_pattern = r"Set milestone ['\"]([^'\"]+)['\"] to (completed|in_progress|blocked) \((\d+)%\)"
            for match in re.finditer(milestone_pattern, response_text, re.IGNORECASE):
                milestone = match.group(1)
                status = match.group(2)
                percentage = int(match.group(3))

                # Use default workflow for MVP
                workflow_id = 'default'

                result = self.session_manager.set_milestone(
                    self.session_id,
                    workflow_id=workflow_id,
                    milestone=milestone,
                    status=status,
                    completion_percentage=percentage
                )

                if result:
                    feedback_parts.append(f"✓ Milestone '{milestone}' → {status} ({percentage}%)")

            # Pattern: Escalate blocker: [description]
            blocker_pattern = r"Escalate blocker:\s*(.+?)(?:\n|$)"
            for match in re.finditer(blocker_pattern, response_text, re.IGNORECASE):
                description = match.group(1).strip()

                # Extract affected agents if mentioned
                affected = ['all']
                for agent in ['cairn', 'koda', 'prax']:
                    if agent in description.lower():
                        if affected == ['all']:
                            affected = []
                        affected.append(agent)

                blocker_id = self.session_manager.escalate_blocker(
                    self.session_id,
                    blocker_description=description,
                    affected_agents=affected,
                    severity='high'
                )

                if blocker_id:
                    feedback_parts.append(f"🚨 Blocker escalated to humans (ID: {blocker_id[:8]})")

        # ===== Phase 4C.1: Task Delegation Tools =====

        # Import TaskDelegationManager
        try:
            from task_delegation_manager import get_task_delegation_manager, TaskDefinition
            task_manager = get_task_delegation_manager(self.session_manager)
        except ImportError:
            task_manager = None

        if task_manager:
            # Pattern: Delegate to [agent]: [description] | Criteria: [criteria] | Priority: [priority] | Canvas: [section]
            if from_agent == 'prax':  # Only Prax can delegate
                # Full delegation pattern
                full_delegate_pattern = r"Delegate to (cairn|koda):\s*(.+?)\s*\|\s*Criteria:\s*(.+?)\s*\|\s*Priority:\s*(critical|high|medium|low)\s*\|\s*Canvas:\s*(\w+)"
                for match in re.finditer(full_delegate_pattern, response_text, re.IGNORECASE):
                    to_agent = match.group(1).lower()
                    description = match.group(2).strip()
                    criteria = match.group(3).strip()
                    priority = match.group(4).lower()
                    canvas_section = match.group(5).strip()

                    task = TaskDefinition(
                        id="",  # Will be generated
                        description=description,
                        success_criteria=criteria,
                        tools_allowed=['web_search', 'analysis'],
                        canvas_section=canvas_section,
                        priority=priority
                    )

                    try:
                        task_id = task_manager.delegate_task(
                            from_agent='prax',
                            to_agent=to_agent,
                            task=task,
                            session_id=self.session_id
                        )
                        feedback_parts.append(f"📋 Task delegated to {to_agent} (ID: {task_id})")

                        # Register in session
                        self.session_manager.register_delegated_task(
                            self.session_id,
                            task_id,
                            {
                                'from_agent': 'prax',
                                'to_agent': to_agent,
                                'description': description,
                                'status': 'pending',
                                'canvas_section': canvas_section
                            }
                        )
                    except Exception as e:
                        feedback_parts.append(f"❌ Delegation failed: {str(e)}")

                # Simple delegation pattern (without full parameters)
                simple_delegate_pattern = r"Delegate to (cairn|koda):\s*([^|]+?)(?:\n|$)"
                for match in re.finditer(simple_delegate_pattern, response_text, re.IGNORECASE):
                    to_agent = match.group(1).lower()
                    description = match.group(2).strip()

                    # Skip if already matched by full pattern
                    if "| Criteria:" in response_text[match.start():match.end()+50]:
                        continue

                    task = TaskDefinition(
                        id="",
                        description=description,
                        success_criteria="Complete the task as described",
                        priority="medium"
                    )

                    try:
                        task_id = task_manager.delegate_task(
                            from_agent='prax',
                            to_agent=to_agent,
                            task=task,
                            session_id=self.session_id
                        )
                        feedback_parts.append(f"📋 Task delegated to {to_agent} (ID: {task_id})")

                        self.session_manager.register_delegated_task(
                            self.session_id,
                            task_id,
                            {
                                'from_agent': 'prax',
                                'to_agent': to_agent,
                                'description': description,
                                'status': 'pending'
                            }
                        )
                    except Exception as e:
                        feedback_parts.append(f"❌ Delegation failed: {str(e)}")

            # Task acknowledgment (Cairn/Koda)
            if from_agent in ['cairn', 'koda']:
                # Pattern: Acknowledge task [task_id]
                ack_pattern = r"Acknowledge task (task_\w+)"
                for match in re.finditer(ack_pattern, response_text, re.IGNORECASE):
                    task_id = match.group(1)
                    if task_manager.acknowledge_task(task_id, from_agent):
                        feedback_parts.append(f"✓ Task {task_id} acknowledged")

                        self.session_manager.update_delegated_task(
                            self.session_id, task_id, {'status': 'acknowledged'}
                        )

                # Pattern: Start task [task_id]
                start_pattern = r"Start task (task_\w+)"
                for match in re.finditer(start_pattern, response_text, re.IGNORECASE):
                    task_id = match.group(1)
                    if task_manager.start_task(task_id, from_agent):
                        feedback_parts.append(f"▶ Task {task_id} started")

                        self.session_manager.update_delegated_task(
                            self.session_id, task_id, {'status': 'in_progress'}
                        )

                # Pattern: Update progress on [task_id]: [percentage]% - [notes]
                progress_pattern = r"Update progress on (task_\w+):\s*(\d+)%\s*-\s*(.+?)(?:\n|$)"
                for match in re.finditer(progress_pattern, response_text, re.IGNORECASE):
                    task_id = match.group(1)
                    percentage = int(match.group(2))
                    notes = match.group(3).strip()

                    if task_manager.update_progress(task_id, from_agent, percentage, notes):
                        feedback_parts.append(f"📊 Task {task_id} progress: {percentage}%")

                # Pattern: Report blocker on [task_id]: [description]
                task_blocker_pattern = r"Report blocker on (task_\w+):\s*(.+?)(?:\n|$)"
                for match in re.finditer(task_blocker_pattern, response_text, re.IGNORECASE):
                    task_id = match.group(1)
                    blocker_desc = match.group(2).strip()

                    if task_manager.report_blocker(task_id, from_agent, blocker_desc, 'high'):
                        feedback_parts.append(f"🚫 Blocker reported on {task_id}")

                        self.session_manager.update_delegated_task(
                            self.session_id, task_id, {'status': 'blocked', 'blocker': blocker_desc}
                        )

                # Pattern: Complete task [task_id]: [result_summary] | Canvas: [content]
                complete_pattern = r"Complete task (task_\w+):\s*(.+?)\s*(?:\|\s*Canvas:\s*(.+))?(?:\n|$)"
                for match in re.finditer(complete_pattern, response_text, re.IGNORECASE | re.DOTALL):
                    task_id = match.group(1)
                    result_summary = match.group(2).strip()
                    canvas_content = match.group(3).strip() if match.group(3) else ""

                    if task_manager.complete_task(task_id, from_agent, result_summary, result_summary, canvas_content):
                        feedback_parts.append(f"✅ Task {task_id} completed")

                        self.session_manager.update_delegated_task(
                            self.session_id, task_id, {'status': 'completed', 'result': result_summary}
                        )

                        # Update canvas section if content provided
                        if canvas_content:
                            task_status = task_manager.get_task_status(task_id)
                            if task_status:
                                task_data = task_manager.tasks.get(task_id)
                                if task_data and task_data.task_definition and task_data.task_definition.canvas_section:
                                    self.session_manager.update_canvas_section(
                                        self.session_id,
                                        task_data.task_definition.canvas_section,
                                        canvas_content,
                                        from_agent
                                    )
                                    feedback_parts.append(f"📝 Canvas section '{task_data.task_definition.canvas_section}' updated")

            # Pattern: Get task status [task_id]
            status_pattern = r"Get task status (task_\w+)"
            for match in re.finditer(status_pattern, response_text, re.IGNORECASE):
                task_id = match.group(1)
                status = task_manager.get_task_status(task_id)
                if status:
                    feedback_parts.append(f"📋 Task {task_id}: {status['status']} ({status['progress_percentage']}%)")
                else:
                    feedback_parts.append(f"❌ Task {task_id} not found")

            # Pattern: List my tasks (for Cairn/Koda)
            if re.search(r'List my tasks', response_text, re.IGNORECASE) and from_agent in ['cairn', 'koda']:
                tasks = task_manager.get_tasks_for_agent(self.session_id, from_agent)
                if tasks:
                    feedback_parts.append(f"📋 Your tasks ({len(tasks)}):")
                    for t in tasks[:5]:
                        feedback_parts.append(f"  - {t['task_id']}: {t['status']}")
                else:
                    feedback_parts.append("📭 No tasks assigned")

            # Pattern: List all tasks (for Prax)
            if re.search(r'List all tasks', response_text, re.IGNORECASE) and from_agent == 'prax':
                tasks = task_manager.get_all_session_tasks(self.session_id)
                if tasks:
                    feedback_parts.append(f"📋 All tasks ({len(tasks)}):")
                    for t in tasks[:10]:
                        feedback_parts.append(f"  - {t['id']} → {t['to_agent']}: {t['status']}")
                else:
                    feedback_parts.append("📭 No tasks in session")

        # ===== Phase 4C.3: External Tool Execution =====

        # Pattern: Use tool [tool_name]: {params}
        tool_pattern = r'Use tool (\w+):\s*(\{[^}]+\})'
        for match in re.finditer(tool_pattern, response_text, re.IGNORECASE):
            tool_name = match.group(1).lower()
            params_str = match.group(2)

            try:
                params = json.loads(params_str)
            except json.JSONDecodeError:
                feedback_parts.append(f"❌ Invalid JSON for tool {tool_name}")
                continue

            # Execute tool via ToolGateway
            try:
                from tool_gateway import get_tool_gateway
                import asyncio

                tool_gateway = get_tool_gateway(session_manager=self.session_manager)

                # Run async tool execution
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(
                        tool_gateway.execute_tool(
                            tool_name=tool_name,
                            params=params,
                            requesting_agent=from_agent,
                            session_id=self.session_id
                        )
                    )
                finally:
                    loop.close()

                if result.status.value == 'success':
                    # Format result based on tool type
                    if tool_name in ['deepseek', 'openai', 'claude_haiku']:
                        result_preview = str(result.result)[:500] + '...' if len(str(result.result)) > 500 else str(result.result)
                        feedback_parts.append(f"🤖 {tool_name} response:\n{result_preview}")
                    elif tool_name == 'web_search':
                        results = result.result.get('results', [])
                        feedback_parts.append(f"🔍 Web search ({len(results)} results):")
                        for r in results[:3]:
                            feedback_parts.append(f"  - {r.get('title', 'No title')}")
                            feedback_parts.append(f"    {r.get('snippet', '')[:100]}...")
                    elif tool_name == 'url_fetch':
                        content = result.result.get('content', '')[:300]
                        feedback_parts.append(f"🌐 Fetched URL:\n{content}...")
                    elif tool_name == 'code_analysis':
                        analysis = result.result
                        feedback_parts.append(f"🔬 Code analysis: {analysis.get('summary', '')}")
                        for issue in analysis.get('issues', [])[:3]:
                            feedback_parts.append(f"  ⚠️ {issue.get('message', '')}")
                    else:
                        feedback_parts.append(f"✓ Tool {tool_name} executed successfully")

                    if result.cost_usd > 0:
                        feedback_parts.append(f"  💰 Cost: ${result.cost_usd:.4f}")

                elif result.status.value == 'denied':
                    feedback_parts.append(f"🚫 Permission denied: {from_agent} cannot use {tool_name}")
                else:
                    feedback_parts.append(f"❌ Tool {tool_name} failed: {result.error}")

            except ImportError:
                feedback_parts.append(f"⚠️ ToolGateway not available")
            except Exception as e:
                feedback_parts.append(f"❌ Tool execution error: {str(e)}")

        # Return combined feedback if any tools were executed
        if feedback_parts:
            return "\n".join(feedback_parts)

        return None


# Example usage and testing
if __name__ == '__main__':
    """
    Test the orchestrator with a simple conversation.
    """
    import sys

    # Check for API key
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print("Error: ANTHROPIC_API_KEY not set")
        print("Set it with: export ANTHROPIC_API_KEY='your-key-here'")
        sys.exit(1)

    # Create orchestrator
    print("Creating orchestrator...")
    orchestrator = AgentOrchestrator()

    # Test Agent A
    print("\n--- Testing Agent A (Koda) ---")
    print("Sending message: 'Hello, what's your role?'")

    for chunk in orchestrator.send_message('a', "Hello, what's your role?"):
        print(chunk, end='', flush=True)

    print("\n\n--- Agent A Status ---")
    print(f"Status: {orchestrator.get_status('a')}")
    print(f"Context length: {len(orchestrator.get_context('a'))} messages")

    # Test document loading
    print("\n--- Testing Document Loading ---")
    sample_doc = """
# Sample Document

This is a sample document for testing.

## Features
- Feature 1
- Feature 2
"""

    orchestrator.load_document('b', sample_doc)
    print("Document loaded into Agent B")

    print("\n--- Testing Agent B (Cairn) ---")
    print("Sending message: 'Summarize the document'")

    for chunk in orchestrator.send_message('b', "Summarize the document"):
        print(chunk, end='', flush=True)

    print("\n\n--- Session Export ---")
    session = orchestrator.export_session()
    print(f"Exported session with {len(session['agents'])} agents")
    print(json.dumps({k: {'context_length': len(v['context'])} for k, v in session['agents'].items()}, indent=2))
