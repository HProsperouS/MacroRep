"""The multi-agent check-in: Nutrition and Workout agents propose, a Reviewer checks
them together, and deterministic validation has the last word before the user does.

See ``graph.py`` for the flow. Agents only read the check-in's frozen snapshot and
return structured output; they never touch the database or the user's plan.
"""
