"""Backward compatibility wrapper for ScoringSystem.

This module provides backward compatibility by re-exporting ScoringSystem from the new location.
"""

from scoring.system import ScoringSystem

__all__ = ['ScoringSystem']
