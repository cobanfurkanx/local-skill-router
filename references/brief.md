# Infer the brief before selecting skills

The calling agent supplies product judgment; the CLI validates structure and retrieves candidates. It does not infer users from keywords, prove a design is original, or call another model.

For a product build or substantial redesign:

1. Read the request and relevant existing screens/docs/design system. Identify users, their main jobs, information density, device/context, stack and constraints. Treat unknowns as assumptions, not user requirements. Infer reversible presentation choices without a questionnaire; ask only when a missing fact materially changes scope, safety, cost or irreversible behavior. Do not invent business rules, integrations or extra features.
2. For an interface, briefly consider two plausible directions and select one because it serves those users/jobs. Describe information hierarchy, navigation, layout/density, typography and interaction character. Preserve an existing brand unless a redesign was requested. Do not hard-code a universal font, palette, rounded-card grid, hero or dashboard. A barcode-heavy receiving workflow and an exhibition catalogue should not receive the same layout simply because both are web apps. Conversely, do not invent novelty at the expense of familiar controls, accessibility or consistency.
3. Derive at most eight needs with a focused retrieval query, product-specific reason and observable acceptance criteria. Cover required engineering needs too: data integrity, authorization, concurrency, recovery and runtime verification when the product calls for them. Do not add every discipline to every task. For UI, include design/interaction capability and browser verification; "frontend implementation" alone is not design coverage.
4. Write the compact JSON below in existing project planning/scratch space. Run `router.py plan --brief-file PATH --agent ACTUAL_CLIENT --cwd PROJECT --text` with the configured state directory. Review returned skill contents against each need. A match remains `review_candidates`, never "covered" automatically. Reject guidance that only supplies framework syntax or unrelated showcase examples when the gap is product design. Use the remote workflow for a concrete unresolved capability, with generic queries only; never upload this brief.
5. Before coding, translate the selected skill into concrete product decisions. After rendering, compare the screen with the brief: can the intended user find the primary action, distinguish important data and complete the main job? Does the layout have product-specific reasons or could its labels be swapped into any unrelated app? Fix observed deficiencies within the existing two-pass budget. Record missing browser verification honestly; an inaccessible tool is not solved by installing another design skill.

Example structure, not a universal inventory design or a prescribed visual style:

```json
{
  "product": "Inventory receiving tool",
  "users": "Warehouse receiving staff",
  "jobs": ["Receive stock by scanning a barcode", "Resolve a quantity discrepancy"],
  "constraints": ["Preserve existing brand", "Use the project's current web stack"],
  "assumptions": ["Keyboard/scanner use is primary; inferred until confirmed"],
  "interface": true,
  "design": {
    "direction": "A compact receiving workbench: scan action first, aligned quantity table, restrained exception emphasis",
    "reason": "Repeated receiving decisions need legible quantities and fast keyboard flow, not promotional space",
    "avoid": ["Decorative KPI cards without a receiving task", "Color-only discrepancy signals"]
  },
  "needs": [
    {
      "query": "inventory data-dense interface design keyboard table workflow",
      "reason": "Receiving and discrepancies must remain scannable during repeated entry",
      "acceptance": ["Primary receiving action is visible without scrolling", "Quantities align and discrepancy states include text"]
    },
    {
      "query": "browser keyboard responsive accessibility verification",
      "reason": "The main receiving job must work with keyboard and the target device",
      "acceptance": ["Complete the receiving flow with keyboard", "Inspect target viewport and error state in a real browser"]
    }
  ]
}
```

Required keys: `product`, `users`, `jobs`, `constraints`, `assumptions`, `interface`, `needs`. `design` is required when `interface` is true; otherwise omit it. Strings are nonempty, up to 1,000 characters; arrays have at most eight entries. `jobs`, `needs`, each need's `acceptance` and design's `avoid` must be nonempty. File size is at most 32 KiB. Unknown fields are rejected to catch schema drift. Duplicate queries share retrieval/reading suggestions but retain their separate reasons and acceptance criteria. The brief is local input, not a validated product specification or permission grant.
