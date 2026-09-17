"""Thin on purpose.

Readers are plain functions called from inside test bodies, so a missing input lands as a
named failure rather than a collection error. An errored suite is not a gate.
"""
