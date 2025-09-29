# Python & Spark Helpers

Most teams are happy using the Builder UI and the YAML files it produces. If you want to automate things in Python or inside a Spark notebook, Polymo exposes a small helper module. The code is short and friendly—you can copy/paste it as-is.

## Loading a connector in Spark

```python
from pyspark.sql import SparkSession
from polymo import ApiReader

spark = SparkSession.builder.getOrCreate()
spark.dataSource.register(ApiReader)

df = (
    spark.read.format("polymo")
    .option("config_path", "./config.yml")  # YAML file you saved earlier
    .option("token", "YOUR_TOKEN")          # Only if the API needs one
    .options(owner="dan1elt0m", repo="polymo")  # Extra values used in templates
    .load()
)

df.show()
```

Key ideas:
- `config_path` points to the YAML file.
- Pass sensitive values (tokens, keys) with `.option(...)` so they never touch the config file.
- You can add as many `.option("name", "value")` calls as you need. They show up inside templates as `{{ options.name }}`.

The `ApiReader` class is what tells Spark how to interpret the config. Register it once per Spark session and you are good to go.
