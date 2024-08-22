import controller.dapr_controller
from controller.graphql_controller import GraphQLController
from controller.dapr_controller import DaprController
from service.DocProcAiService import DocProcAiService
from fastapi import FastAPI
import uvicorn

if __name__ == "__main__":
    service = DocProcAiService()

    app = FastAPI()

    dapr_controller = controller.dapr_controller.DaprController(app, service)
    graphql_controller = controller.graphql_controller.GraphQLController(app, service)

    uvicorn.run(app, host="0.0.0.0", port=9901)
