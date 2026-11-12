from fastapi import HTTPException, status


class AppException(HTTPException):
    pass


def not_found(resource: str = "Resource"):
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{resource} not found")


def forbidden():
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden")


def bad_request(detail: str):
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
