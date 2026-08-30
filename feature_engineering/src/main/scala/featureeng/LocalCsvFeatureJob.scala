package featureeng

import org.apache.spark.sql.SparkSession

/** Runs Features.computeVelocityFeatures against the real IEEE-CIS CSV on a
  * local Spark session, for real benchmark numbers and a real feature
  * output to feed the rest of the pipeline -- standing in for the actual
  * Databricks run (see FeatureEngineeringJob) until a Databricks Community
  * Edition workspace is wired up with real Snowflake credentials.
  *
  * Writes Parquet, not Delta: this local run doesn't carry a delta-core
  * dependency (FeatureEngineeringJob's `.format("delta")` string resolves
  * against whatever's on the Databricks cluster's classpath, needing
  * nothing at compile time here). A separate step converts this Parquet
  * output to a real local Delta table via Python's `deltalake` package,
  * which `feature_store` already depends on.
  */
object LocalCsvFeatureJob {

  private val requiredColumns = Seq("TransactionID", "isFraud", "TransactionDT", "TransactionAmt", "card1", "P_emaildomain")

  def main(args: Array[String]): Unit = {
    require(args.length == 2, "usage: LocalCsvFeatureJob <input_csv> <output_parquet_path>")
    val inputCsv = args(0)
    val outputPath = args(1)

    val spark = SparkSession.builder().appName("local-feature-benchmark").master("local[*]").getOrCreate()
    try {
      val start = System.nanoTime()

      val transactions = spark.read
        .option("header", "true")
        .option("inferSchema", "true")
        .csv(inputCsv)
        .select(requiredColumns.head, requiredColumns.tail: _*)

      val rowCount = transactions.count()
      val features = Features.computeVelocityFeatures(transactions)
      features.write.mode("overwrite").parquet(outputPath)

      val elapsedSeconds = (System.nanoTime() - start) / 1e9
      // scalastyle:off println
      println(s"BENCHMARK rows=$rowCount elapsedSeconds=$elapsedSeconds outputPath=$outputPath")
      // scalastyle:on println
    } finally spark.stop()
  }
}
