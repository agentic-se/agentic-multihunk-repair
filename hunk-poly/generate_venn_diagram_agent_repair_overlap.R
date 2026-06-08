#!/usr/bin/env Rscript
# ==============================================================================
# Venn Diagram Generator for Bug Repair Overlap Across Coding Agents
# ==============================================================================
# This script generates high-quality Venn diagrams showing the overlap of
# bugs successfully repaired by four different coding agents:
# - Gemini CLI
# - Qwen Code
# - Claude Code
# - OpenAI Codex
#
# For TOSEM paper submission.
# ==============================================================================

# Load required libraries
library(VennDiagram)
library(jsonlite)
library(grid)

# ==============================================================================
# Configuration
# ==============================================================================

# Input and output paths
input_json <- "fixed_bugs_by_agent.json"
output_pdf <- "plots/venn_diagram_agent_repair_overlap.pdf"

# Color palette (professional, colorblind-friendly)
colors <- c(
  "#E69F00",  # Orange - Gemini CLI
  "#56B4E9",  # Sky Blue - Qwen Code
  "#009E73",  # Green - Claude Code
  "#D55E00"   # Red-Orange - OpenAI Codex
)

# ==============================================================================
# Load and Process Data
# ==============================================================================

cat("Loading bug repair data from JSON...\n")

# Read JSON file
data <- fromJSON(input_json)

# Extract bug lists for each agent
gemini_bugs <- data$gemini_cli
qwen_bugs <- data$qwen_code
claude_bugs <- data$claude_code
codex_bugs <- data$openai_codex

cat(sprintf("  Gemini CLI: %d bugs fixed\n", length(gemini_bugs)))
cat(sprintf("  Qwen Code: %d bugs fixed\n", length(qwen_bugs)))
cat(sprintf("  Claude Code: %d bugs fixed\n", length(claude_bugs)))
cat(sprintf("  OpenAI Codex: %d bugs fixed\n", length(codex_bugs)))

# ==============================================================================
# Generate Venn Diagram - PDF (Vector Format)
# ==============================================================================

cat("\nGenerating high-resolution PDF Venn diagram...\n")

venn.plot <- venn.diagram(
  x = list(
    "Gemini CLI" = gemini_bugs,
    "Qwen Code" = qwen_bugs,
    "Claude Code" = claude_bugs,
    "OpenAI Codex" = codex_bugs
  ),
  filename = NULL,
  output = FALSE,

  # Colors and transparency
  fill = colors,
  alpha = 0.5,

  # Category names
  category.names = c("Gemini CLI", "Qwen Code", "Claude Code", "OpenAI Codex"),

  # Label settings
  cex = 2.5,                    # Size of numbers in diagram
  fontface = "bold",            # Bold numbers
  fontfamily = "sans",          # Sans-serif font

  # Category label settings
  cat.cex = 2.5,                # Size of category labels
  cat.fontface = "bold",        # Bold category names
  cat.fontfamily = "sans",      # Sans-serif font
  cat.default.pos = "outer",    # Position category names outside

  # Line settings
  lwd = 2,                      # Line width for circles
  lty = "solid",                # Solid lines
  col = "black",                # Black circle borders

  # Disable logging
  disable.logging = TRUE
)

# Save to PDF using grid graphics
pdf(output_pdf, width = 14, height = 14)
grid.draw(venn.plot)
dev.off()

cat(sprintf("  Saved: %s\n", output_pdf))

# ==============================================================================
# Summary Statistics
# ==============================================================================

cat("\n")
cat(paste(rep("=", 70), collapse=""))
cat("\n")
cat("Summary Statistics\n")
cat(paste(rep("=", 70), collapse=""))
cat("\n")

# Calculate unique bugs fixed by any agent
all_bugs <- unique(c(gemini_bugs, qwen_bugs, claude_bugs, codex_bugs))
cat(sprintf("Total unique bugs fixed by at least one agent: %d\n", length(all_bugs)))

# Calculate intersection of all four agents
common_all <- Reduce(intersect, list(gemini_bugs, qwen_bugs, claude_bugs, codex_bugs))
cat(sprintf("Bugs fixed by ALL four agents: %d\n", length(common_all)))

cat("\nVenn diagram generation complete!\n")
cat(paste(rep("=", 70), collapse=""))
cat("\n")
