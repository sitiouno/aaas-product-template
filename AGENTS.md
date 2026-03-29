# AI Coding Assistant Rules

This file applies to all AI coding assistants (Claude Code, Cursor, Copilot, Windsurf, etc.)

## Non-Negotiable Rules

1. **Max 600 lines per file** — split by responsibility if approaching limit
2. **No monolithic modules** — one file = one clear purpose
3. **Run tests before claiming done** — `pytest tests/ -v`
4. **Never modify protected files** without explicit user unlock:
   - `product_app/security.py`
   - `product_app/models.py`
   - `product_app/stripe_billing.py`
   - `product_app/database.py`

## Code Standards

- **Clean code**: descriptive names, single-responsibility functions (max 30 lines), no dead code
- **Security first**: validate inputs, sanitize outputs, no secrets in client code
- **DRY but not premature**: extract shared logic only when used 3+ times
- **YAGNI**: build what's needed now, not what might be needed later
- **Test behavior**: test what the code does, not how it does it

## File Structure

Follow the modular structure in CLAUDE.md. Key principle:
- JavaScript: one module per workspace section
- CSS: split by concern (theme, layout, components, sections)
- Python: split by domain (routes, rendering, auth, billing, agents)

## When Adding Features

1. Check if an existing module handles this concern
2. If yes, add to that module (respecting 600-line limit)
3. If no, create a new focused module
4. Add tests for new behavior
5. Update CLAUDE.md if the structure changes

## Agent Development

See `product_app/research/hello_world.py` for the pattern.
See the Getting Started section in the workspace for vibe coding prompts.
