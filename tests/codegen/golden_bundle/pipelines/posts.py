"""Lakeflow Declarative Pipeline for posts."""

from pyspark import pipelines as dp
from pyspark.sql import SparkSession
from jsonplaceholder_demo.source import JsonplaceholderDemoSource

spark = SparkSession.getActiveSession()
spark.dataSource.register(JsonplaceholderDemoSource)


@dp.table(name="posts")
def posts():
    return spark.read.format("posts_source").load()
