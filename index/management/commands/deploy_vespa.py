# index/management/commands/deploy_vespa.py

# python manage.py deploy_vespa

from django.core.management.base import BaseCommand
from django.conf import settings
from vespa.application import Vespa
from vespa.package import (
    ApplicationPackage,
    Field,
    Schema,
    Document,
    HNSW,
    RankProfile,
    Component,
    Parameter,
    FieldSet,
    GlobalPhaseRanking,
    Function,
)
from vespa.deployment import VespaDocker
import io
import requests
import logging
import json
import docker
import sys


def custom_deploy_data(
        self,
        application: ApplicationPackage,
        data,
        debug: bool,
        max_wait_configserver: int,
        max_wait_application: int,
        docker_timeout: int,
) -> Vespa:
    """
    Deploys an Application Package as zipped data

    :param application: Application package
    :param max_wait_configserver: Seconds to wait for the config server to start
    :param max_wait_application: Seconds to wait for the application deployment

    :raises RuntimeError: Exception if deployment fails
    :return: A Vespa connection instance
    """
    self._run_vespa_engine_container(
        application_name=application.name,
        container_memory=self.container_memory,
        volumes=self.volumes,
        debug=debug,
        docker_timeout=docker_timeout,
    )
    self.wait_for_config_server_start(max_wait=max_wait_configserver)

    r = requests.post(
        "http://{}:{}/application/v2/tenant/default/prepareandactivate".format(
            "172.18.0.2",
            self.cfgsrv_port
        ),
        headers={"Content-Type": "application/zip"},
        data=data,
        verify=False,
    )
    logging.debug("Deploy status code: {}".format(r.status_code))
    if r.status_code != 200:
        raise RuntimeError(
            "Deployment failed, code: {}, message: {}".format(
                r.status_code, json.loads(r.content.decode("utf8"))
            )
        )

    app = Vespa(url="172.18.0.3", port=7080, application_package=application)
    app.wait_for_application_up(max_wait=max_wait_application)

    print("Finished deployment.", file=self.output)
    return app


VespaDocker._deploy_data = custom_deploy_data


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        package = ApplicationPackage(
            name="hybridsearch",
            schema=[
                Schema(
                    name="doc",
                    document=Document(
                        fields=[
                            Field(name="id", type="string", indexing=["summary"]),
                            Field(name="title", type="string", indexing=["index", "summary"], index="enable-bm25"),
                            Field(name="body", type="string", indexing=["index", "summary"], index="enable-bm25",
                                  bolding=True),
                            Field(name="embedding", type="tensor<float>(x[384])",
                                  indexing=['input title . " " . input body', "embed", "index", "attribute"],
                                  ann=HNSW(distance_metric="angular"), is_document_field=False),
                        ]
                    ),
                    fieldsets=[FieldSet(name="default", fields=["title", "body"])],
                    rank_profiles=[
                        RankProfile(name="bm25", inputs=[("query(q)", "tensor<float>(x[384])")],
                                    functions=[Function(name="bm25sum", expression="bm25(title) + bm25(body)")],
                                    first_phase="bm25sum"),
                        RankProfile(name="semantic", inputs=[("query(q)", "tensor<float>(x[384])")],
                                    first_phase="closeness(field, embedding)"),
                        RankProfile(name="fusion", inherits="bm25", inputs=[("query(q)", "tensor<float>(x[384])")],
                                    first_phase="closeness(field, embedding)", global_phase=GlobalPhaseRanking(
                                expression="reciprocal_rank_fusion(bm25sum, closeness(field, embedding))",
                                rerank_count=1000)),
                    ],
                )
            ],
            components=[
                Component(id="e5", type="hugging-face-embedder", parameters=[
                    Parameter("transformer-model", {
                        "url": "https://github.com/vespa-engine/sample-apps/raw/master/simple-semantic-search/model/e5-small-v2-int8.onnx"}),
                    Parameter("tokenizer-model", {
                        "url": "https://raw.githubusercontent.com/vespa-engine/sample-apps/master/simple-semantic-search/model/tokenizer.json"}),
                ]),
            ],
        )

        # vespa_docker = VespaDocker.from_container_name_or_id(f'vespa-cfg')
        # VespaDocker('http://localhost', 7070, 'vespa-cfg', 'fc0c677cc309f3002e3183621cd34d5ed6ea28ce52f100cb62b1880aca770d4a', 0, 'vespaengine/vespa')
        # vespa_docker = VespaDocker('http://vespa-cfg', 7070, 'vespa-cfg', 'fc0c677cc309f3002e3183621cd34d5ed6ea28ce52f100cb62b1880aca770d4a', 0, 'vespaengine/vespa')
        # print(vespa_docker)

        # vespa_app = Vespa(url="http://vespa-cfg", port=7070)
        # index = vespa_app.deploy(application_package=package)

        # Initialize VespaDocker with the running container's URL and port
        # vespa_docker = VespaDocker(
        #     host="http://vespa-cfg",  # Vespa container host
        #     port=7070,  # Port number
        #     output_file=None,  # No output file needed
        #     docker_cmd=None,  # No need to run a new Docker container
        #     container_memory=4294967296,  # Memory allocation (4GB for example)
        #     image_name='vespaengine/vespa'  # Docker image name used by the running container
        # )

        # vespa_docker = HostedVespaDocker.from_container_name_or_id(f'vespa-cfg', url="http://vespa-cfg:8080")
        # index = vespa_docker.deploy(application_package=package)

        # vespa_instance = HostedVespa(f'vespa-cfg', url="http://localhost:8080")
        # print(vespa_instance)
        # print("Deploying application package to Vespa instance...")
        # index = vespa_instance.deploy_application_package(package)

        vespa_docker = VespaDocker.from_container_name_or_id(f'vespa-cfg')
        # VespaDocker('http://localhost', 7070, 'vespa-cfg', 'fc0c677cc309f3002e3183621cd34d5ed6ea28ce52f100cb62b1880aca770d4a', 0, 'vespaengine/vespa')
        vespa_docker.url = "http://vespa-cfg"
        print(vespa_docker)
        index = vespa_docker.deploy(application_package=package)

        # python manage.py deploy_vespa

        docs = [
            {"fields": {"id": "doc1", "title": "Vespa for Hybrid Search",
                        "body": "Vespa supports BM25 and semantic search together."}},
            {"fields": {"id": "doc2", "title": "Introduction to Vespa",
                        "body": "Vespa is an open-source search engine for high scale applications."}},
        ]

        # Feed documents to Vespa
        for doc in docs:
            index.feed_data_point(schema="doc", data_id=doc["fields"]["id"], fields=doc["fields"])

        # Query the Vespa instance using BM25 ranking
        result = index.query(query="Vespa search engine", query_properties={"ranking": "bm25"}, hits=10)

        # Output the results
        print(result.hits)
