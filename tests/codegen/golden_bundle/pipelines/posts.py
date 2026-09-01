"""posts — Lakeflow Declarative Pipeline source (Databricks Asset Bundle).

Registers the `JsonplaceholderDemoSource` data source from `jsonplaceholder_demo.source`
(built on `jsonplaceholder_demo.client`) and wires it to a `@dp.table`; edit this
file freely — it is not read by polymo again.
"""

from pyspark import pipelines as dp  # noqa: E402
from pyspark.sql import SparkSession  # noqa: E402
from jsonplaceholder_demo import client as _client_module  # noqa: E402
from jsonplaceholder_demo import source as _source_module  # noqa: E402
from pyspark import cloudpickle  # noqa: E402

# Spark pickles the DataSource/reader below BY REFERENCE (they live in
# `jsonplaceholder_demo.source`, not `__main__`), so executors would otherwise
# need `jsonplaceholder_demo` importable on their own sys.path — but
# databricks.yml's root_path only extends the driver's. Registering both
# modules for by-value pickling ships their code inside the pickle payload
# instead, so executors never need to import either of them. `source`
# imports from `client` internally, and by-value serialization follows
# that import, so `client` needs registering too even though this file
# never calls it directly.
cloudpickle.register_pickle_by_value(_client_module)
cloudpickle.register_pickle_by_value(_source_module)

spark = SparkSession.getActiveSession()
spark.dataSource.register(_source_module.JsonplaceholderDemoSource)


@dp.table(name="posts")
def posts():
    return spark.read.format("posts_source").load()
