from .adapter import SecurityObservation
from .models import SecurityObservationModel


def normalize(observation: SecurityObservation) -> SecurityObservationModel:
    return SecurityObservationModel(
        observation_id=observation.observation_id,
        path=observation.path,
        category=observation.category,
        severity=observation.severity,
        line_number=observation.line_number,
        content_sha256=observation.content_sha256,
    )
