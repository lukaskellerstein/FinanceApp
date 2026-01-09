# Finance App - Development Guidelines

## Running the App via MCP

Use the MCP tools to launch, control, and test the Finance App:

### Launch the App
```
mcp__finance-app-control__launch_app
```

### Get UI Snapshot
```
mcp__finance-app-control__get_snapshot
```
Returns all widgets with properties (object_name, type, visible, enabled, etc.) and available menu actions.

### Get Screenshot
```
mcp__playwright__browser_take_screenshot
```
Takes a visual screenshot of the current page/app state. Useful for visual verification and debugging UI issues.

### Interact with the App
- **Click**: `mcp__finance-app-control__click(object_name)`
- **Fill text**: `mcp__finance-app-control__fill(object_name, text)`
- **Clear text**: `mcp__finance-app-control__clear(object_name)`
- **Get text**: `mcp__finance-app-control__get_text(object_name)`
- **Checkbox**: `mcp__finance-app-control__set_checkbox(object_name, checked)`
- **Combo box**: `mcp__finance-app-control__select_combo(object_name, value)`
- **Tab selection**: `mcp__finance-app-control__select_tab(object_name, index)`
- **Table data**: `mcp__finance-app-control__get_table_data(object_name)`
- **Menu actions**: `mcp__finance-app-control__trigger_action(object_name)`

### Close the App
```
mcp__finance-app-control__close_app
```

### Workspace Requirements

The app is automatically launched on **workspaces 100-120** (dedicated for MCP testing). This allows multiple Claude Code terminals to run independent test instances without conflicts.

**Child windows/dialogs**: All dialogs and child windows must open on the **same workspace as the parent window**. This is ensured by passing proper `parent` to Qt widgets (e.g., `QMessageBox.information(self, ...)` not `QMessageBox.information(None, ...)`).

For detailed implementation info, see: [docs/testability_via_regolith.md](docs/testability_via_regolith.md)

### Widget Naming for MCP Testability

**Every interactive widget MUST have `setObjectName()` set** - widgets without object names are invisible to MCP and cannot be tested.

**Naming conventions:**
```python
# Input fields: {purpose}_input
self.ticker_input.setObjectName("ticker_input")

# Buttons: {purpose}_button
self.add_button.setObjectName("add_button")

# Labels: {purpose}_label
self.status_label.setObjectName("status_label")

# Pages/containers: {name}_page, {name}_tabs
self.setObjectName("stocks_watchlist_page")

# Tables: {name}_table
self.table.setObjectName("stocks_assets_table")

# Dynamic widgets (with variable): {type}_{identifier}_{widget}
view_btn.setObjectName(f"watchlist_view_{symbol.lower()}_button")
delete_btn.setObjectName(f"delete_{symbol.lower()}_button")

# Menu actions: action_{name}
home_action.setObjectName("action_home")
```

**Rules:**
- Use `snake_case` for all object names
- Be descriptive: `login_button` not `btn1`
- For dynamic items, include identifier: `delete_aapl_button`
- Menu actions must have object names to be triggerable via MCP

For detailed implementation info, see: [docs/testability_via_mcp.md](docs/testability_via_mcp.md)

---

## CRITICAL RULES

### 1. ALWAYS CLOSE THE APP WHEN FINISHED TESTING

**DO NOT FORGET** to call `mcp__finance-app-control__close_app` when you are done testing or when the task is complete. Leaving the app running wastes resources and can cause issues with subsequent launches.

### 2. TEST EVERY FUNCTIONALITY BEFORE REPORTING TASK COMPLETION

**NEVER** tell the user "task is done" without:
1. Launching the app
2. Navigating to the relevant UI components
3. Verifying the implemented/modified functionality works correctly
4. Checking for errors in the UI state
5. Closing the app

Each change must be validated through the MCP interface before considering the task complete.

---

## Core Philosophy

Write code that is **simple, maintainable, and production-ready**. Prioritize clarity over cleverness, and always leave the codebase cleaner than you found it.

## Key Principles

1. **Simplicity First**: Choose the simplest solution that meets requirements (KISS principle)
2. **Consistency**: Maintain tech stack consistency unless there's strong justification for change
3. **Maintainability**: Prioritize code clarity and self-documentation over clever solutions
4. **Scalability**: Design for growth without premature optimization
5. **Best Practices**: Follow established patterns, idioms, and community conventions
6. **Clean Architecture**: Apply SOLID principles and maintain separation of concerns
7. **Quality First**: Continuous refactoring and cleanup are not optional

## Code Quality Standards

### SOLID Principles (Non-negotiable)

- **Single Responsibility**: Each class/function has exactly one reason to change
- **Open/Closed**: Open for extension, closed for modification
- **Liskov Substitution**: Subtypes must be substitutable for their base types
- **Interface Segregation**: Many specific interfaces beat one general-purpose interface
- **Dependency Inversion**: Depend on abstractions, not concrete implementations

### Clean Code Practices

**Code Organization:**

- Keep functions small (< 20 lines ideally, < 100 lines maximum)
- One level of abstraction per function
- Use meaningful, pronounceable names (avoid abbreviations unless widely known)
- Self-documenting code is the goal; comments explain "why", not "what"

**Code Quality:**

- **DRY Principle**: Don't Repeat Yourself - eliminate duplication through abstraction
- **YAGNI**: You Aren't Gonna Need It - don't add features speculatively
- Write code that's easy to delete, not easy to extend
- Prefer composition over inheritance

**Error Handling:**

- Fail fast and explicitly
- Use typed errors/exceptions with clear messages
- Never silently ignore errors
- Validate inputs at system boundaries

## Development Workflow

### Before Writing Code
1. Understand the requirement completely - ask clarifying questions if needed

2. Identify impacted areas of the codebase
3. Plan the simplest approach that satisfies requirements

### While Writing Code

1. **Write clean code from the start** - don't plan to "clean it up later"
2. **Test as you go** - verify changes work before moving on
3. **Refactor continuously** - improve code structure immediately when you see issues
4. **Remove dead code** - delete unused functions, variables, imports, and commented code

### After Writing Code

1. **Review and update comments** - ensure they reflect current implementation
2. **Clean up imports** - remove unused dependencies
3. **Verify tests pass** - run existing tests and add new ones if needed
4. **Check for side effects** - ensure changes don't break other functionality

## Technology Stack

### Frontend & UI

**JavaScript/TypeScript:**

- Package Manager: `npm`
- Runtime: Node.js
- Framework: React
- UI Components: shadcn-ui (https://ui.shadcn.com/), Radix UI primitives
- Styling: Tailwind CSS
- Type Safety: TypeScript with strict mode enabled

### Backend

**Node.js:**

- Package Manager: `npm`
- API Framework: Express.js
- Bundler: `esbuild` (target both CommonJS and ESM if possible, otherwise ESM only)

**Python:**

- **CRITICAL**: Use `uv` exclusively - NEVER use `pip` directly
- Virtual Environment: `uv venv` followed by `source .venv/bin/activate`
- Dependency Management: `uv sync` (not `pip install`)
- CLI Reference: `uv --help`
- **AVOID**: `hatchling.build` in pyproject.toml
- API Framework: FastAPI with Uvicorn
- Type Hints: Use type annotations consistently (Python 3.10+ syntax)

**Go:**

- Use only when justified (performance-critical services, system tools)

### Scripting & Automation

- **Default**: Python for all scripts
- **Avoid**: Bash/Shell scripts (unless trivial one-liners), PowerShell
- Keep scripts simple, documented, and testable

### Operating System

- **Primary**: Linux (Ubuntu LTS preferred)
- **Containers**: Alpine or distroless for production images
- **Alternative**: Windows only when specifically required

### AI & Machine Learning

**Frameworks:**

- ML/DL: PyTorch (primary), avoid TensorFlow
- Model Hub: Hugging Face for pretrained models
- Embeddings: sentence-transformers

**Agent Development:**

- **Preferred**: Claude Agent SDK (https://docs.claude.com/en/docs/agent-sdk/overview)
- **Alternative**: LangChain >= 1.0.0 + LangGraph >= 1.0.0 (https://docs.langchain.com/)
- Keep agent chains simple and debuggable

### Infrastructure & DevOps

**Containerization:**

- Docker for local development and production
- Multi-stage builds for minimal image sizes
- .dockerignore to exclude unnecessary files

**Orchestration:**

- Kubernetes via Google Kubernetes Engine (GKE)
- Helm for K8s resource templating
- Keep manifests DRY and well-documented

**Infrastructure as Code:**

- Terraform for cloud resources
- Version control all IaC configurations
- Use modules for reusability

**Networking:**

- Traefik as ingress/reverse proxy

## Code Review Checklist

Before considering code complete, verify:

- [ ] All unused code removed (functions, variables, imports, comments)
- [ ] Comments updated to reflect current implementation
- [ ] No code duplication (DRY principle applied)
- [ ] Functions are small and focused (single responsibility)
- [ ] Error handling is explicit and comprehensive
- [ ] Type safety maintained (TypeScript/Python type hints)
- [ ] Tests written/updated and passing
- [ ] No hardcoded values (use configuration/environment variables)
- [ ] Security best practices followed (no secrets in code, input validation, etc.)
- [ ] Performance considered (no obvious bottlenecks)

## Communication Guidelines

**Context:**

- Assume 20+ years of software engineering experience
- Skip basic explanations unless specifically requested
- Be direct and technical in communication
- Ask for clarification when requirements are ambiguous

**Code Explanations:**

- Focus on "why" decisions were made, not "what" the code does
- Highlight tradeoffs and alternatives considered
- Point out areas that may need future attention

## Anti-Patterns to Avoid

- ❌ Leaving commented-out code "just in case"
- ❌ Adding TODO comments 
- ❌ Copying and pasting code instead of abstracting
- ❌ Premature optimization
- ❌ Over-engineering simple solutions
- ❌ Ignoring compiler/linter warnings
- ❌ Writing code without understanding its purpose
- ❌ Implementing features "we might need someday"

## Remember

> "Code is read far more often than it is written." - Guido van Rossum

> "Any fool can write code that a computer can understand. Good programmers write code that humans can understand." - Martin Fowler

Write code you'd be proud to maintain in 2 years.

