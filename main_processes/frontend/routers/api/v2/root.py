from fastapi import APIRouter


router = APIRouter(prefix="/v2")


def register_apis():
    from .models.root import router as models_router
    from .tasks.root import router as tasks_router
    from .pipelines.root import router as pipelines_router

    router.include_router(models_router)
    router.include_router(pipelines_router)
    router.include_router(tasks_router)


register_apis()
