# Archive - Golden Library

This directory contains archived plans and compressed handoffs following the LLM-friendly PRD management system.

## Structure

```
archive/
├── plans/              # Archived CURRENT_PLAN.md files
│   ├── 2026-01-14_phase4_realtime.md (future)
│   └── ...
└── README.md           # This file

.golden_library/        # Compressed handoffs (sibling to archive/)
├── compressed/         # SLIM/V4Z compressed plans
├── metadata/           # Handoff metadata
└── index.json          # Searchable index
```

## Workflow

### When Phase Completes

1. **Compress the plan:**
   ```bash
   python3 -m golden_library.compress CURRENT_PLAN.md
   # Output: handoff://a3f8e92c
   ```

2. **Archive:**
   ```bash
   mv CURRENT_PLAN.md archive/plans/$(date +%Y-%m-%d)_phase4_realtime.md
   ```

3. **Create new plan:**
   ```bash
   cat > CURRENT_PLAN.md <<EOF
   ---
   phase: 5
   previous_handoff: a3f8e92c
   ...
   EOF
   ```

4. **Commit:**
   ```bash
   git add CURRENT_PLAN.md archive/
   git commit -m "Phase 4 complete, starting Phase 5"
   ```

## Benefits

**For LLMs:**
- Single source of truth (CURRENT_PLAN.md)
- Compressed history (token efficient)
- Clear handoff between instances
- Searchable decision log

**For Humans:**
- Git-tracked evolution
- Visual timeline (3D viewer)
- Audit trail of decisions
- Cross-repo pattern library

## Related

- See: `CURRENT_PLAN.md` for active work
- See: `PRD_3D_VIEWER_INTEGRATION.md` for Phase 3 spec
- Pattern inspired by: prax-chat workflow
