from pydantic import BaseModel, Field

from app.models.content_report import ReportTargetType


class ContentReportCreate(BaseModel):
    target_type: ReportTargetType
    target_id: int
    reason: str = Field(min_length=1, max_length=1000)
