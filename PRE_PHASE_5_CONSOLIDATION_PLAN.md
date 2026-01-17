# Pre-Phase 5 Consolidation Plan

**Objective:** Solidify Phase 4C foundation before Phase 5, preparing for high-stakes investor demo where investors PARTICIPATE in a collaborative workspace session that delivers real value.

**Demo Vision:** Investors don't just watch a product pitch—they JOIN a live multi-user AI workspace session where Prax/Cairn/Koda help solve a REAL problem for their portfolio companies, demonstrating immediate ROI.

---

## Part 1: Technical Consolidation

### 1.1 Test Suite Consolidation

**Goal:** Single command runs all 54 tests, generates report

**Tasks:**
- [ ] Create `run_all_tests.py` master test runner
- [ ] Add test timing and summary statistics
- [ ] Generate HTML test report for investor deck
- [ ] Add CI/CD integration (GitHub Actions)
- [ ] Create test coverage report

**Files to create:**
```
tests/
├── run_all_tests.py          # Master runner
├── test_report.html          # Generated report
└── conftest.py               # Shared fixtures
```

**Test inventory:**
| Phase | Test File | Tests |
|-------|-----------|-------|
| 4C.1 | test_phase4c1_delegation.py | 9 |
| 4C.2 | test_phase4c2_canvas.py | 9 |
| 4C.3 | test_phase4c3_tools.py | 9 |
| 4C.4 | test_phase4c4_database.py | 9 |
| 4C.5 | test_phase4c5_demo.py | 9 |
| 4C.6 | test_phase4c6_config.py | 9 |
| **Total** | | **54** |

---

### 1.2 Edge Cases & TODOs

**Goal:** Audit codebase for incomplete implementations

**Audit targets:**
- [ ] Search for `TODO`, `FIXME`, `XXX`, `HACK` comments
- [ ] Check all `try/except` blocks have proper error messages
- [ ] Verify all async functions handle cancellation
- [ ] Test WebSocket reconnection scenarios
- [ ] Test session expiration handling
- [ ] Test concurrent user limits (12+ users)
- [ ] Test large message handling (>100KB)
- [ ] Test rapid-fire events (rate limiting)

**Known edge cases to address:**
| Area | Edge Case | Priority |
|------|-----------|----------|
| Canvas | Concurrent edits to same section | High |
| Delegation | Circular delegation prevention | High |
| Database | Connection pool exhaustion | Medium |
| Demo | Recording during network issues | Medium |
| Config | Malformed CLAUDE.md handling | Low |
| Hooks | Slow hook blocking event loop | Medium |

---

### 1.3 Code Deduplication

**Goal:** DRY principles, reduce maintenance burden

**Audit areas:**
- [ ] WebSocket message handlers (dashboard_server.py) - extract patterns
- [ ] Session validation (repeated in multiple methods)
- [ ] JSON serialization (multiple to_dict implementations)
- [ ] Error response formatting
- [ ] Audit log entry creation
- [ ] Agent permission checks

**Refactoring candidates:**
```python
# Before (repeated pattern)
if not session_manager:
    return {'error': 'Session manager not available'}
session = session_manager.get_session(session_id)
if not session:
    return {'error': 'Session not found'}

# After (extracted utility)
def require_session(session_manager, session_id):
    """Validate session exists, return (session, error_dict)"""
    ...
```

---

### 1.4 Error Handling Improvements

**Goal:** Graceful degradation, informative errors

**Tasks:**
- [ ] Add error codes to all error responses (e.g., `E001_SESSION_NOT_FOUND`)
- [ ] Create error catalog documentation
- [ ] Add retry logic for transient failures (DB, API calls)
- [ ] Implement circuit breaker for external tools
- [ ] Add request ID tracking for debugging
- [ ] Log stack traces to file (not console in production)
- [ ] Add user-friendly error messages for frontend

**Error response format:**
```json
{
  "error": true,
  "code": "E042_TOOL_RATE_LIMITED",
  "message": "DeepSeek API rate limit reached. Retrying in 30s.",
  "retry_after": 30,
  "request_id": "req_abc123"
}
```

---

### 1.5 Documentation Update

**Goal:** Comprehensive docs for investors and developers

**Documentation to create/update:**

| Document | Purpose | Audience |
|----------|---------|----------|
| README.md | Quick start, architecture overview | Developers |
| INVESTOR_DEMO_GUIDE.md | How to run investor demo | Internal |
| API_REFERENCE.md | WebSocket API documentation | Developers |
| ARCHITECTURE.md | System design, data flow diagrams | Technical investors |
| DEPLOYMENT.md | Production deployment guide | DevOps |
| CHANGELOG.md | Version history with features | All |

**Diagrams to create:**
- [ ] System architecture (agents, DB, WebSocket)
- [ ] Data flow (user → agent → tools → response)
- [ ] Delegation hierarchy (Prax → Cairn → Koda)
- [ ] Demo mode recording flow

---

## Part 2: Demo-Ready Enhancements

### 2.1 Investor Demo Scenario Design

**Goal:** Create sector-specific demo templates that deliver REAL value to each investor

**The "2011 Social Media" Framing:**
> "Remember 2011? Social media was 'for kids.' Businesses that took it seriously then have 100,000 followers now. Businesses that waited have 500. AI is that moment. Right now."

---

#### Template System Architecture

Templates are stored in `src/demo_templates/` and loaded by WorkspaceConfig:

```
src/demo_templates/
├── __init__.py
├── base_template.py          # Abstract template class
├── food_services.py          # Coffee shops, restaurants
├── software_security.py      # Security companies
├── legal.py                  # Law firms
├── real_estate.py            # Real estate investors
├── construction.py           # Construction companies
└── template_registry.py      # Template discovery & loading
```

**Adding new templates:** Create new `.py` file inheriting from `BaseTemplate`, auto-discovered on startup.

---

#### Template 1: ☕ Food Services (Coffee Shops)
**Target investor:** Coffee shop owner (5 locations)
**File:** `food_services.py`

**Pain points:** Inventory waste, staffing, menu optimization, location performance variance

**Demo flow:**
1. **Input:** "Here's last month's sales data for my 5 coffee shop locations"
2. **Prax:** "I'll coordinate analysis across locations. Cairn will identify patterns, Koda will generate actionable recommendations."
3. **Cairn:** Analyzes data → "Location 3 sells 40% more oat milk lattes than others. Location 1 has 23% food waste on pastries."
4. **Koda:** Generates recommendations → "Redistribute oat milk inventory. Reduce pastry orders at Location 1 by 20%."
5. **Prax:** Synthesizes → "Here's your location-specific action plan for next month."

**Deliverable:** Location performance report + inventory rebalancing recommendations

**Time saved:** 4 hours/week → 5 minutes
**Annual value:** ~$10,000 in reduced waste + manager time

---

#### Template 2: 🔐 Software Security
**Target investor:** Security company owner
**File:** `software_security.py`

**Pain points:** Threat analysis speed, compliance documentation, scaling expertise

**Demo flow:**
1. **Input:** "New client needs SOC2 compliance assessment for their SaaS platform"
2. **Prax:** "Security assessment requires architecture review and compliance mapping. Cairn handles threat modeling, Koda generates documentation."
3. **Cairn:** Researches → "Based on their tech stack (AWS, Node.js, PostgreSQL), here are the top 10 relevant CVEs and their SOC2 control mappings."
4. **Koda:** Generates → "SOC2 compliance checklist with 47 controls. 12 require immediate attention based on their architecture."
5. **Prax:** Delivers → "Client-ready assessment report with prioritized remediation roadmap."

**Deliverable:** SOC2 gap analysis + remediation priorities

**SECURE IMPLEMENTATION POINTS TO HIGHLIGHT:**
- "Notice how all data stays in YOUR environment—we're not sending client data to external APIs"
- "Every AI action is logged in the audit trail (show Phase 4C.4 database)"
- "Tool permissions are controlled per-agent (show Phase 4C.3 gateway)"
- "You can offer AI-assisted security audits to YOUR clients using this same platform"

**Time saved:** 8-hour assessment → 30 minutes
**Revenue opportunity:** Offer AI-augmented assessments at premium pricing

---

#### Template 3: ⚖️ Legal Services
**Target investor:** Law firm owner
**File:** `legal.py`

**Pain points:** Research time, document drafting, client intake bottleneck

**Demo flow:**
1. **Input:** "Client needs an NDA for a software development partnership"
2. **Prax:** "Contract drafting requires jurisdiction research and clause selection. Cairn researches requirements, Koda drafts."
3. **Cairn:** Researches → "California law. Key considerations: IP ownership, non-solicitation enforceability, term limits."
4. **Koda:** Drafts → "NDA template with 12 standard clauses + 3 California-specific provisions. Highlighted areas requiring client input."
5. **Prax:** Reviews → "Draft complete. Flagged 2 clauses that may need attorney review for this specific partnership type."

**Deliverable:** First-draft NDA ready for attorney review

**Time saved:** 2 hours → 5 minutes per document
**Capacity increase:** Paralegals handle 5x more intake

---

#### Template 4: 🏠 Real Estate
**Target investor:** Real estate investor
**File:** `real_estate.py`

**Pain points:** Property analysis time, market research, investment decision speed

**Demo flow:**
1. **Input:** "Analyze 123 Main St, Austin TX for investment potential"
2. **Prax:** "Investment analysis requires market data, comparable sales, and ROI modeling. Cairn researches, Koda calculates."
3. **Cairn:** Researches → "Neighborhood: 12% appreciation last 3 years. Comparable sales: $425K-$475K. Rental market: $2,200-$2,500/month."
4. **Koda:** Calculates → "Buy at $400K: Rental ROI 6.8% (cash flow positive month 1). Flip ROI: 18% assuming $50K renovation."
5. **Prax:** Synthesizes → "Investment summary with risk factors: school district rezoning pending, new development 2 blocks away."

**Deliverable:** Property investment analysis with ROI scenarios

**Time saved:** 4 hours research → 10 minutes
**Competitive advantage:** Analyze 10 properties while competitors analyze 1

---

#### Template 5: 🏗️ Construction
**Target investor:** Construction company owner
**File:** `construction.py`

**Pain points:** Bid accuracy, project timeline estimation, subcontractor coordination

**Demo flow:**
1. **Input:** "Commercial office renovation, 5,000 sq ft, downtown location"
2. **Prax:** "Bid preparation requires scope breakdown, material estimation, and timeline planning. Cairn scopes, Koda estimates."
3. **Cairn:** Analyzes → "Project phases: Demo (1 week), Electrical (2 weeks), HVAC (2 weeks), Finishing (3 weeks). Critical path: HVAC inspection."
4. **Koda:** Estimates → "Materials: $127,000. Labor: $89,000. Permits: $4,500. Contingency (15%): $33,000. Total bid: $253,500."
5. **Prax:** Delivers → "Bid package with phase breakdown, risk factors (permit delays, material availability), and payment schedule."

**Deliverable:** Preliminary bid + project timeline + risk assessment

**Time saved:** 2 days → 1 hour
**Win rate improvement:** More accurate bids = better margins

---

#### Template Registry Implementation

```python
# src/demo_templates/template_registry.py

class TemplateRegistry:
    """Auto-discovers and manages demo templates."""

    templates = {}

    @classmethod
    def register(cls, template_class):
        """Decorator to register a template."""
        cls.templates[template_class.SECTOR_ID] = template_class
        return template_class

    @classmethod
    def get_template(cls, sector_id: str):
        """Get template by sector ID."""
        return cls.templates.get(sector_id)

    @classmethod
    def list_templates(cls):
        """List all available templates."""
        return [
            {
                'id': t.SECTOR_ID,
                'name': t.SECTOR_NAME,
                'description': t.DESCRIPTION,
                'pain_points': t.PAIN_POINTS
            }
            for t in cls.templates.values()
        ]
```

**Adding a new template:**
```python
# src/demo_templates/healthcare.py

@TemplateRegistry.register
class HealthcareTemplate(BaseTemplate):
    SECTOR_ID = "healthcare"
    SECTOR_NAME = "Healthcare / Medical Practice"
    DESCRIPTION = "Patient intake, scheduling, compliance documentation"
    PAIN_POINTS = ["HIPAA compliance", "scheduling efficiency", "patient communication"]

    async def run_demo(self, session, input_data):
        # Template-specific demo flow
        ...
```

---

### 2.2 Demo UX Polish

**Goal:** Flawless first impression

**Visual improvements:**
- [ ] Add loading states for all async operations
- [ ] Smooth animations for canvas updates
- [ ] Agent "thinking" indicators with estimated time
- [ ] Highlight when delegation happens (visual cue)
- [ ] Sound effects for key moments (optional, toggleable)
- [ ] Dark/light theme toggle in header
- [ ] "Demo Mode Active" banner with recording indicator

**Quality of life:**
- [ ] One-click demo start button
- [ ] Pre-populated demo scenarios (dropdown)
- [ ] "Reset Demo" button for quick restart
- [ ] Investor name personalization in responses
- [ ] Auto-save session state every 30 seconds

---

### 2.3 Demo Recording Enhancements

**Goal:** Every investor demo becomes marketing material

**Improvements:**
- [ ] Auto-start recording when demo mode enabled
- [ ] Add investor name/company to recording metadata
- [ ] Generate executive summary from recording
- [ ] Export as branded PDF report
- [ ] Email recording link post-meeting
- [ ] Add timestamps to key moments automatically

---

## Part 3: Phase 5 Additions (Based on 4C Work)

### 3.1 Workflow Presets (Leveraging Delegation)

**Built on:** Phase 4C.1 Hierarchical Delegation

**Presets to implement:**
| Preset | Agents | Use Case |
|--------|--------|----------|
| Due Diligence | Prax + Cairn + Koda | Company research |
| Code Review | Cairn + Koda | PR/architecture review |
| Market Research | Prax + Cairn | Competitive analysis |
| Debug Session | Koda (primary) | Bug hunting |
| Design Sprint | Cairn (primary) | Architecture planning |

**Implementation:**
```python
# One-click workflow launch
session_manager.launch_preset(
    session_id="...",
    preset="due_diligence",
    context={"company": "Acme Corp"}
)
```

---

### 3.2 Live Collaboration Analytics (Leveraging Database)

**Built on:** Phase 4C.4 Conversation Database

**Real-time metrics:**
- Messages per minute (human vs agent)
- Agent response latency
- Delegation success rate
- Tool usage breakdown
- Cost per session (token tracking)

**Investor-facing dashboard:**
- "Your session used $0.42 in AI compute"
- "3 research tasks completed in parallel"
- "Saved ~2 hours of manual research"

---

### 3.3 Session Replay (Leveraging Demo Mode)

**Built on:** Phase 4C.5 Live Demo Mode

**Enhancements:**
- Playback recordings at 1x, 2x, 4x speed
- Jump to highlights
- Export key moments as GIFs
- Embed replay in pitch decks

---

### 3.4 Workspace Templates (Leveraging Config)

**Built on:** Phase 4C.6 Configuration

**Templates:**
- "Investor Meeting" template (pre-configured agents, branding)
- "Technical Review" template (Cairn-focused)
- "Brainstorm" template (high creativity settings)

**One-click apply:**
```
/apply-template investor-meeting
```

---

## Part 4: Investor Demo Checklist

### Pre-Meeting Setup
- [ ] Test all 54 tests pass
- [ ] Verify WebSocket server stable
- [ ] Check API keys have sufficient credits
- [ ] Pre-load demo scenarios
- [ ] Test screen sharing setup
- [ ] Prepare backup demo (recorded video)
- [ ] Send calendar invite with join link

### During Meeting
- [ ] Start recording immediately
- [ ] Personalize greeting with investor name
- [ ] Let investor type a query themselves
- [ ] Show real-time collaboration (not scripted)
- [ ] Highlight cost savings in real-time
- [ ] Generate deliverable they can keep
- [ ] Export recording link before meeting ends

### Post-Meeting
- [ ] Send recording + transcript
- [ ] Send generated report/deliverable
- [ ] Follow up with relevant demo scenarios
- [ ] Collect feedback on experience

---

## Part 5: Implementation Timeline

### Day 1: Test Consolidation
- [ ] Create run_all_tests.py
- [ ] Fix any failing tests
- [ ] Generate coverage report
- [ ] Document test results

### Day 2: Edge Cases & Error Handling
- [ ] Audit TODOs and FIXMEs
- [ ] Implement error codes
- [ ] Add retry logic
- [ ] Test edge cases

### Day 3: Code Cleanup & Deduplication
- [ ] Extract common patterns
- [ ] Refactor repeated code
- [ ] Add type hints where missing
- [ ] Remove dead code

### Day 4: Documentation
- [ ] Write README.md
- [ ] Create ARCHITECTURE.md
- [ ] Document WebSocket API
- [ ] Create investor demo guide

### Day 5: Demo Polish
- [ ] Implement demo scenarios
- [ ] Add UX improvements
- [ ] Test full demo flow
- [ ] Record backup demo video

### Day 6: Final Testing
- [ ] Full regression test
- [ ] Load testing (12+ users)
- [ ] Security audit (basic)
- [ ] Performance benchmarks

---

## Success Criteria

**Technical:**
- [ ] All 54 tests pass
- [ ] <100ms WebSocket latency
- [ ] Zero crashes in 1-hour session
- [ ] Handles 12 concurrent users

**Demo:**
- [ ] Investor can join in <30 seconds
- [ ] Demo scenarios complete in <10 minutes
- [ ] Generates tangible deliverable
- [ ] Recording exports correctly

**Investor Impression:**
- [ ] "I didn't expect AI to work together like that"
- [ ] "This is actually useful for my portfolio"
- [ ] "Can we use this for [specific use case]?"
- [ ] "When can I invest?"

---

## Appendix: File Inventory

**Core modules (Phase 4C):**
```
src/
├── workspace_session_manager.py  (2000+ lines)
├── agent_orchestrator.py         (1500+ lines)
├── canvas_sync_manager.py        (500+ lines)
├── tool_gateway.py               (900+ lines)
├── conversation_database.py      (870 lines)
├── demo_recorder.py              (600+ lines)
└── workspace_config.py           (500+ lines)
```

**Test files:**
```
test_phase4c1_delegation.py
test_phase4c2_canvas.py
test_phase4c3_tools.py
test_phase4c4_database.py
test_phase4c5_demo.py
test_phase4c6_config.py
```

**Server:**
```
dashboard_server.py               (5000+ lines)
```

---

*This consolidation plan transforms a technical achievement into an investor-ready product that delivers value in the room, not just promises.*
