from typing import Generic, TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class APIResponse(BaseModel, Generic[DataT]):
    success: bool
    message: str
    data: DataT | None = None


def success_response(data: DataT, message: str = "success") -> APIResponse[DataT]:
    return APIResponse(success=True, message=message, data=data)
