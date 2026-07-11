from pydantic import BaseModel


class HealthData(BaseModel):
    status: str
    service: str
    environment: str


class DatabaseHealthData(BaseModel):
    status: str
    database: str
