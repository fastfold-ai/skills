# Mermaid Syntax Rules

Use these rules to maximize render reliability across light/dark themes.

## IDs and Labels

- IDs must not contain spaces.
  - Good: `designPipeline`, `workflow_stage`, `FoldStep`
  - Bad: `design pipeline`
- Quote labels that include special characters (`()`, `:`, `,`, brackets).
  - Good: `A["Step 1: Prepare (inputs)"]`
- Avoid reserved IDs: `end`, `graph`, `subgraph`, `flowchart`.
  - Good: `endNode[End]`

## Edges and Subgraphs

- Quote edge labels with special characters.
  - Good: `A -->|"O(1) lookup"| B`
- Use explicit subgraph ID and label.
  - Good: `subgraph prepStage [Preparation Stage]`

## Styling and Interactivity

- Do not use explicit color styles (`style`, `classDef` with color fills/strokes).
- Do not use `click` handlers.
- Keep renderer defaults for theme-safe output.

## Practical Authoring Tips

- Prefer flowcharts for default process explanations.
- Keep nodes short and verb-first (for example, `FetchResults`, `RunSimulation`).
- Keep diagrams compact; split only when complexity is too high.
- If Mermaid parsing fails, simplify labels first before changing topology.
