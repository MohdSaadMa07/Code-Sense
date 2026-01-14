from pydantic import BaseModel

class DocumentMetadata(BaseModel):
    title: str
    description: str = None
