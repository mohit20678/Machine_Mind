"""Endpoints for registering and managing machines."""
from fastapi import APIRouter, Response

from backend.schemas.api import MachineCreate, MachineOut, MachineUpdate
from database import models

router = APIRouter(prefix="/api/machines", tags=["machines"])


@router.get("", response_model=list[MachineOut])
def list_machines():
    return models.list_machines()


@router.post("", response_model=MachineOut, status_code=201)
def create_machine(body: MachineCreate):
    return models.create_machine(body.machine_id, body.name, body.machine_type, body.location)


@router.get("/{machine_pk}", response_model=MachineOut)
def get_machine(machine_pk: int):
    machine = models.get_machine(machine_pk)
    if machine is None:
        raise models.NotFoundError("That machine does not exist.")
    return machine


@router.put("/{machine_pk}", response_model=MachineOut)
def update_machine(machine_pk: int, body: MachineUpdate):
    return models.update_machine(machine_pk, body.name, body.machine_type, body.location)


@router.delete("/{machine_pk}", status_code=204, response_class=Response)
def delete_machine(machine_pk: int):
    models.delete_machine(machine_pk)
    return Response(status_code=204)
