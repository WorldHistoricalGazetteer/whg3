# index/vespa.py

from django.conf import settings
#import datasets as hf_datasets

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

package = ApplicationPackage(
    name="hybridsearch",
    schema=[
        Schema(
            name="doc",
            document=Document(
                fields=[
                    Field(name="id", type="string", indexing=["summary"]),
                    Field(
                        name="title",
                        type="string",
                        indexing=["index", "summary"],
                        index="enable-bm25",
                    ),
                    Field(
                        name="body",
                        type="string",
                        indexing=["index", "summary"],
                        index="enable-bm25",
                        bolding=True,
                    ),
                    Field(
                        name="embedding",
                        type="tensor<float>(x[384])",
                        indexing=[
                            'input title . " " . input body',
                            "embed",
                            "index",
                            "attribute",
                        ],
                        ann=HNSW(distance_metric="angular"),
                        is_document_field=False,
                    ),
                ]
            ),
            fieldsets=[FieldSet(name="default", fields=["title", "body"])],
            rank_profiles=[
                RankProfile(
                    name="bm25",
                    inputs=[("query(q)", "tensor<float>(x[384])")],
                    functions=[
                        Function(name="bm25sum", expression="bm25(title) + bm25(body)")
                    ],
                    first_phase="bm25sum",
                ),
                RankProfile(
                    name="semantic",
                    inputs=[("query(q)", "tensor<float>(x[384])")],
                    first_phase="closeness(field, embedding)",
                ),
                RankProfile(
                    name="fusion",
                    inherits="bm25",
                    inputs=[("query(q)", "tensor<float>(x[384])")],
                    first_phase="closeness(field, embedding)",
                    global_phase=GlobalPhaseRanking(
                        expression="reciprocal_rank_fusion(bm25sum, closeness(field, embedding))",
                        rerank_count=1000,
                    ),
                ),
            ],
        )
    ],
    components=[
        Component(
            id="e5",
            type="hugging-face-embedder",
            parameters=[
                Parameter(
                    "transformer-model",
                    {
                        "url": "https://github.com/vespa-engine/sample-apps/raw/master/simple-semantic-search/model/e5-small-v2-int8.onnx"
                    },
                ),
                Parameter(
                    "tokenizer-model",
                    {
                        "url": "https://raw.githubusercontent.com/vespa-engine/sample-apps/master/simple-semantic-search/model/tokenizer.json"
                    },
                ),
            ],
        )
    ],
)

index = Vespa(url='http://localhost', port=settings.VESPA_QUERY_PORT)
index.deploy(application_package=package)



# dataset = hf_datasets.load_dataset("BeIR/nfcorpus", "corpus", split="corpus", streaming=True)
# vespa_feed = dataset.map(
#     lambda x: {
#         "id": x["_id"],
#         "fields": {"title": x["title"], "body": x["text"], "id": x["_id"]},
#     }
# )


docs = [
    {
        "fields": {
            "id": "doc1",
            "title": "Vespa for Hybrid Search",
            "body": "Vespa supports BM25 and semantic search together."
        }
    },
    {
        "fields": {
            "id": "doc2",
            "title": "Introduction to Vespa",
            "body": "Vespa is an open-source search engine for high scale applications."
        }
    }
]

# Feed documents to Vespa
for doc in docs:
    index.feed_data_point(schema="doc", data_id=doc["fields"]["id"], fields=doc["fields"])

# Query the Vespa instance using BM25 ranking
result = index.query(
    query="Vespa search engine",
    query_properties={"ranking": "bm25"},
    hits=10
)

# Output the results
print(result.hits)
