"""posts — Lakeflow Declarative Pipeline source (Databricks Asset Bundle).

Registers the `JsonplaceholderDemoSource` data source from `jsonplaceholder_demo.source`
(built on `jsonplaceholder_demo.client`) and wires it to a `@dp.table`; edit this
file freely — it is not read by polymo again.
"""

from pyspark import pipelines as dp  # noqa: E402
from pyspark.sql import SparkSession  # noqa: E402
from jsonplaceholder_demo.source import JsonplaceholderDemoSource  # noqa: E402

# `databricks.yml` builds `src/jsonplaceholder_demo` into a wheel and installs it via
# the pipeline's `environment.dependencies`, so `jsonplaceholder_demo` is importable
# on the driver AND every executor — no by-value pickling needed.
spark = SparkSession.getActiveSession()
spark.dataSource.register(JsonplaceholderDemoSource)


@dp.table(name="posts")
def posts():
    return spark.read.format("posts_source").load()
