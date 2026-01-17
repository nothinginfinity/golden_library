# Investor Demo Guide

## The Pitch

> "Remember 2011? Social media was 'for kids.' Businesses that took it seriously then have 100,000 followers now. Businesses that waited have 500. **AI is that moment. Right now.**"

This demo shows investors what collaborative AI looks like in action - not a pitch deck, but **real value delivered in the room**.

---

## Pre-Demo Setup (30 min before)

### Technical Checklist

- [ ] Server running: `python3 dashboard_server.py`
- [ ] Test WebSocket connection: `ws://localhost:8080/ws`
- [ ] API keys verified (DeepSeek, OpenAI if used)
- [ ] All 57 tests passing: `python3 run_all_tests.py`
- [ ] Demo scenarios pre-loaded
- [ ] Screen sharing tested
- [ ] Backup demo video ready

### Environment

```bash
# Verify server
curl http://localhost:8080/health

# Check API credits
python3 -c "import os; print('DeepSeek:', bool(os.getenv('DEEPSEEK_API_KEY')))"
```

### Load Demo Template

Based on investor's industry:
- Coffee shops → `food_services` template
- Security → `software_security` template
- Law firms → `legal` template
- Real estate → `real_estate` template
- Construction → `construction` template

---

## Demo Flow (10-15 minutes)

### 1. The Hook (1 min)

**Say:** "Before I show you anything, I want you to think about a problem your portfolio companies face. Something that takes hours of research or analysis."

**Wait for their answer.** This is the problem you'll solve live.

### 2. Live Session (8-10 min)

**Create session with investor name:**
```json
{
  "type": "create_session",
  "user_id": "investor",
  "display_name": "[Investor Name]"
}
```

**Start recording:**
```json
{
  "type": "start_demo",
  "title": "[Investor Name] - [Problem] Demo",
  "branding": {"company_name": "[Their Company]"}
}
```

**Let them type a query themselves.** This is crucial - they feel ownership.

**Example queries by sector:**

| Sector | Example Query |
|--------|---------------|
| Coffee | "Analyze this sales data for my 5 coffee shops and tell me where to cut waste" |
| Security | "New client needs SOC2 assessment for their SaaS platform" |
| Legal | "Draft an NDA for a software development partnership in California" |
| Real Estate | "Analyze 123 Main St, Austin TX for investment potential" |
| Construction | "Prepare a bid for a 5,000 sq ft office renovation downtown" |

**Narrate what's happening:**
- "Watch Prax coordinate the team..."
- "Cairn is now researching [specific thing]..."
- "Koda is generating the [deliverable]..."
- "Notice how they're working in parallel - that's hours compressed to minutes"

### 3. Deliverable (2 min)

**Export something they can keep:**
- PDF report
- Spreadsheet analysis
- Draft document
- Action plan

**Say:** "This is yours. We generated this in [X] minutes. How long would this normally take?"

### 4. Close (2 min)

**Highlight key moments:**
- Time saved
- Cost saved
- Competitive advantage

**The question:** "What if your portfolio companies could do this for their clients?"

---

## Sector-Specific Scripts

### ☕ Coffee Shops / Food Services

**Target:** Owner with 3-10 locations

**Pain points:** Inventory waste, staffing, location variance

**Demo flow:**
1. Input sales data (can be sample if they don't have it)
2. Prax coordinates: "I'll have Cairn analyze patterns, Koda generate recommendations"
3. Cairn: "Location 3 sells 40% more oat milk lattes. Location 1 has 23% pastry waste."
4. Koda: "Recommended actions: Redistribute oat milk, reduce pastry orders at L1 by 20%"
5. Prax: "Here's your location-specific action plan"

**Deliverable:** Location performance report + inventory recommendations

**Value prop:** "This analysis would take your manager 4 hours. We did it in 5 minutes."

---

### 🔐 Software Security

**Target:** Security company owner

**Pain points:** Assessment speed, compliance documentation, scaling expertise

**Demo flow:**
1. Input: Client's tech stack (AWS, Node.js, PostgreSQL - sample is fine)
2. Prax: "Security assessment requires threat modeling + compliance mapping"
3. Cairn: "Top 10 relevant CVEs for this stack. SOC2 control mappings."
4. Koda: "47 controls checklist. 12 require immediate attention."
5. Prax: "Client-ready assessment with prioritized remediation"

**Security-specific callouts:**
- "All data stays in YOUR environment"
- "Every action is in the audit log" (show it)
- "Tool permissions are per-agent controlled" (show gateway)

**Deliverable:** SOC2 gap analysis + remediation roadmap

**Value prop:** "8-hour assessment → 30 minutes. Now YOU can offer AI-assisted audits."

---

### ⚖️ Legal Services

**Target:** Law firm owner

**Pain points:** Research time, document drafting, intake bottleneck

**Demo flow:**
1. Input: "NDA for software development partnership"
2. Prax: "Contract drafting requires jurisdiction research + clause selection"
3. Cairn: "California law. Key considerations: IP ownership, non-solicitation limits."
4. Koda: "Draft NDA with 12 standard clauses + 3 CA-specific provisions"
5. Prax: "Flagged 2 clauses for attorney review in this partnership type"

**Important:** Always include the disclaimer that AI assists but doesn't replace attorney review.

**Deliverable:** First-draft NDA ready for review

**Value prop:** "2 hours → 5 minutes per document. Paralegals handle 5x more intake."

---

### 🏠 Real Estate

**Target:** Real estate investor

**Pain points:** Analysis time, market research, decision speed

**Demo flow:**
1. Input: "Analyze [address] for investment potential"
2. Prax: "Investment analysis needs market data + comparable sales + ROI modeling"
3. Cairn: "12% appreciation last 3 years. Comparables: $425K-$475K. Rental: $2,200-$2,500/mo"
4. Koda: "Buy at $400K: Rental ROI 6.8%. Flip ROI: 18% with $50K renovation"
5. Prax: "Risk factors: School rezoning pending, new development 2 blocks away"

**Deliverable:** Investment analysis with ROI scenarios

**Value prop:** "Analyze 10 properties while competitors analyze 1"

---

### 🏗️ Construction

**Target:** Construction company owner

**Pain points:** Bid accuracy, timeline estimation, coordination

**Demo flow:**
1. Input: "Bid for 5,000 sq ft office renovation, downtown"
2. Prax: "Bid prep needs scope breakdown + materials + timeline"
3. Cairn: "Phases: Demo (1wk), Electrical (2wk), HVAC (2wk), Finishing (3wk). Critical path: HVAC inspection"
4. Koda: "Materials: $127K. Labor: $89K. Permits: $4.5K. Contingency 15%: $33K. Total: $253.5K"
5. Prax: "Bid package with phase breakdown, risk factors, payment schedule"

**Deliverable:** Preliminary bid + timeline + risk assessment

**Value prop:** "2 days → 1 hour. More accurate bids = better margins"

---

## Troubleshooting

### If something fails during demo

**Don't panic.** Say: "Let me show you something interesting - watch how the system handles this."

Then:
1. Acknowledge the issue
2. Show the error handling (graceful degradation)
3. Retry or pivot to backup

### Backup options

1. **Pre-recorded demo** in `/demos/backup_demo.mp4`
2. **Simpler query** that uses fewer external tools
3. **Focus on the architecture** - show the code, explain the vision

### Common issues

| Issue | Solution |
|-------|----------|
| Slow response | "The LLM is thinking - watch the delegation in real-time" |
| API rate limit | Switch to backup model or pre-cached response |
| WebSocket disconnect | Refresh, sessions persist in database |
| Unexpected output | "This is real AI, not scripted - let's refine the query" |

---

## Post-Demo (5 min)

### Immediately

1. **Export recording:** Send link before they leave
2. **Send deliverable:** The PDF/report they can show their team
3. **Follow-up calendar invite:** Book next meeting while in room

### Within 24 hours

1. Email with:
   - Recording link
   - Generated deliverable
   - Relevant sector demo scenarios
   - Pricing/partnership info

2. Feedback survey (short, 3 questions)

---

## Key Talking Points

### On cost

"Every query costs about $0.05-0.50 depending on complexity. That analysis we just did? Under $1. What's your hourly rate for that work today?"

### On security

"All processing happens in your environment. We don't see your data. The audit log captures everything for compliance."

### On competition

"Your competitors are asking the same questions you just asked. The difference is whether you're using AI to answer them in 5 minutes or having analysts spend 5 hours."

### On adoption

"Start with one use case. The coffee shop owner started with inventory analysis. Now they use it for staffing, menu optimization, and customer insights."

---

## Demo Metrics to Highlight

| Metric | What to show |
|--------|--------------|
| Time saved | Stopwatch running, compare to manual |
| Cost per query | Show in real-time: "This query: $0.42" |
| Parallel work | "3 agents working simultaneously" |
| Accuracy | "Cross-referenced 12 sources in 30 seconds" |

---

## Success Indicators

After a good demo, investors say:
- ✅ "I didn't expect AI to work together like that"
- ✅ "This is actually useful for my portfolio"
- ✅ "Can we use this for [specific use case]?"
- ✅ "When can I invest?"

Red flags:
- ⚠️ "This seems like ChatGPT" → Emphasize multi-agent coordination
- ⚠️ "How do I know it's accurate?" → Show sources, audit log
- ⚠️ "My team won't use this" → Discuss change management, training

---

## Recording Checklist

Demo recordings become marketing material. Before each demo:

- [ ] Investor name in title
- [ ] Branding configured
- [ ] Highlight key moments
- [ ] Clean exit (proper stop_demo)
- [ ] Export immediately after
