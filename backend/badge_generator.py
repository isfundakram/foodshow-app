from fastapi.responses import HTMLResponse
from fastapi import APIRouter

router = APIRouter()

@router.get("/badge")
async def badge_preview(name: str, company: str):
    return HTMLResponse(
        f"""
        <html>
        <body style="border:1px solid black;padding:20px;width:300px;">
            <h2>{name}</h2>
            <h4>{company}</h4>
        </body>
        </html>
        """
    )
