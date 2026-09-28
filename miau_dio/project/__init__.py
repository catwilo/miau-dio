"""Project package -- domain model for miau-dio projects.

Re-exports Project, Track and ProjectError so callers can import them
from miau_dio.project directly.
"""
from miau_dio.project.model import Project, ProjectError, Track

__all__ = ["Project", "ProjectError", "Track"]
