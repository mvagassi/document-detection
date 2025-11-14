from fastapi import APIRouter, Depends
from schemas.document.document_checker import SDocumentChecker
from controllers.document.document_checker import DocumentController
from helpers.exceptions import json_response
from http import HTTPStatus
from helpers.logging import logging

router = APIRouter()

@router.post("/document_checker")
async def document_checker(params: SDocumentChecker = Depends()):
    try:
        status, data, msg = await DocumentController.document_checker(params)
        return json_response(HTTPStatus.OK if status else HTTPStatus.BAD_REQUEST, msg, data, status)
    except Exception as e:
        logging.log_error({
            "module": __name__,
            "function": "get_all_department", 
            "error": "Error fetching department", 
            "detail": str(e)
        })
        return json_response(HTTPStatus.INTERNAL_SERVER_ERROR, f"Internal Server Error: {str(e)}", data=None, success=False)
    

