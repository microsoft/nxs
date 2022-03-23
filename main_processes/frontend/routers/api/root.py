from fastapi import APIRouter
from main_processes.frontend.args import parse_args

router = APIRouter(prefix="/api")

args = parse_args()

if args.enable_v1_api:

    @router.get("", status_code=200)
    def api_root():
        return {}


def register_apis():
    from .v2.root import router as v2_router

    router.include_router(v2_router)

    if args.enable_v1_api:
        from .v1.root import router as v1_router, register_root_apis

        register_root_apis(router)
        router.include_router(v1_router)


register_apis()
