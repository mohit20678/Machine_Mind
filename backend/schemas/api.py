"""Shapes of the data the API accepts and returns (Pydantic models).

FastAPI uses these to check incoming data and to build the response and the
documentation page at /docs.
"""
from pydantic import BaseModel, ConfigDict


class MachineCreate(BaseModel):
    machine_id: str
    name: str
    machine_type: str
    location: str | None = None


class MachineUpdate(BaseModel):
    name: str
    machine_type: str
    location: str | None = None


class MachineOut(BaseModel):
    id: int                 # record number (used in URLs and as machine_pk)
    machine_id: str         # the Machine ID text, for example PUMP-01
    name: str
    machine_type: str
    location: str | None
    created_at: str
    analysis_count: int


class AlertOut(BaseModel):
    id: int
    analysis_id: int
    machine_pk: int
    machine_code: str
    machine_name: str
    message: str
    acknowledged: bool
    created_at: str
    filename: str
    prediction_label: str
    anomaly_score: float
    is_mock: bool


class AnalysisOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: int
    machine_pk: int
    machine_code: str
    machine_name: str
    filename: str
    duration_seconds: float | None
    sample_rate: int | None
    channels: int | None
    prediction_label: str
    anomaly_score: float
    threshold: float | None
    model_name: str
    model_version: str
    is_mock: bool
    created_at: str
    alert_id: int | None


class AnalysisPage(BaseModel):
    total: int              # how many analyses match the filters (not only this page)
    items: list[AnalysisOut]


class AnalysisResult(BaseModel):
    analysis: AnalysisOut
    alert: AlertOut | None
    score_note: str         # what the score means, according to the model
    warnings: list[str]
    mock_warning: str | None  # filled only for placeholder results


class StatsOut(BaseModel):
    total_machines: int
    total_analyses: int
    normal_count: int
    abnormal_count: int
    mock_analyses: int
    latest_analysis_at: str | None
    total_alerts: int
    open_alerts: int


class ModelStatus(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    mode: str
    is_real: bool
    model_name: str
    model_version: str
    threshold: float | None
    score_note: str
    message: str


class HealthOut(BaseModel):
    status: str
    database: str
