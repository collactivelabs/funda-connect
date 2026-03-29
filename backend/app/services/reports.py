from datetime import datetime
from uuid import UUID


def build_learner_report_reference(learner_id: UUID, generated_at: datetime) -> str:
    return f"FC-LRP-{generated_at.strftime('%Y%m%d')}-{str(learner_id).split('-')[0].upper()}"
