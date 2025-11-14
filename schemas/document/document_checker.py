from fastapi import UploadFile
from pydantic import BaseModel

class SDocumentChecker(BaseModel):
    file: UploadFile