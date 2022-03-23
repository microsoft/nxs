import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from args import parse_args
from nxs_utils.common import create_dir_if_needed

args = parse_args()
create_dir_if_needed(args.tmp_dir)

app = FastAPI(
    title="Nxs Frontend",
    version="0.1.0",
    contact={"name": "Loc Huynh", "email": "lohuynh@microsoft.com"},
)

# app.mount("/static", StaticFiles(directory="tmp"), name="static")

from main_processes.frontend.routers.api.root import router as api_router

app.include_router(api_router)


@app.get("/")
def root():
    return {}


if __name__ == "__main__":
    # uvicorn.run("app:app", host="0.0.0.0", port=args.port, reload=True)
    uvicorn.run("app:app", host="0.0.0.0", port=args.port, reload=False)
