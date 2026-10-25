"""Endpoints for uploading a recording for analysis and for reading saved analyses."""
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend.schemas.api import AnalysisOut, AnalysisPage, AnalysisResult
from backend.services import audio_utils
from backend.services.analysis_service import analyse_recording
from database import models
from ml_integration.predictor import get_predictor

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


@router.post("", response_model=AnalysisResult, status_code=201)
def create_analysis(
    machine_pk: int = Form(...),
    file: UploadFile = File(...),
    predictor=Depends(get_predictor),
):
    """Upload a WAV recording for a machine. It is checked, analysed and saved."""
    limit_bytes = int(audio_utils.MAX_FILE_SIZE_MB * 1024 * 1024)
    data = file.file.read(limit_bytes + 1)  # read one byte too many, so we can notice a huge file
    if len(data) > limit_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"The file is too large. The maximum size is {audio_utils.MAX_FILE_SIZE_MB} MB.",
        )
    return analyse_recording(data, file.filename, machine_pk, predictor)


@router.get("", response_model=AnalysisPage)
def list_analyses(
    machine_pk: int | None = None,
    prediction: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """Saved analyses, newest first. Optional filters: machine, prediction, dates (UTC)."""
    filters = dict(
        machine_pk=machine_pk,
        prediction_label=prediction,
        date_from=date_from,
        date_to=date_to,
    )
    items = models.list_analyses(limit=limit, offset=offset, **filters)
    total = models.count_analyses(**filters)
    return {"total": total, "items": items}


@router.get("/{analysis_id}", response_model=AnalysisOut)
def get_analysis(analysis_id: int):
    analysis = models.get_analysis(analysis_id)
    if analysis is None:
        raise models.NotFoundError("That analysis does not exist.")
    return analysis
