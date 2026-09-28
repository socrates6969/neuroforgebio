"""Multiverse sweeps (BUILD-GUIDE 3.6; BLUEPRINT §3.5; market/new-ideas.md #4).

``service`` expands a parameter grid over a published PipelineVersion into N runs on the 3.3
queue and builds the comparison report. Design decision (reproducibility): every grid point is
published as its own immutable, content-addressed PipelineVersion; runs never carry parameter
overrides. See ``service`` for the reasoning.
"""
