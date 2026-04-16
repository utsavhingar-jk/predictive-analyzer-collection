"""Shared explainability schemas used across prediction responses."""

from pydantic import BaseModel, Field


class FeatureDriver(BaseModel):
    feature_name: str
    display_name: str
    feature_value: float
    contribution: float
    direction: str  # "increases_prediction" | "decreases_prediction"


class PredictionOutputDrivers(BaseModel):
    output_name: str
    predicted_value: float
    drivers: list[FeatureDriver] = Field(default_factory=list)
