package featureeng

import org.apache.spark.sql.SparkSession

import java.io.FileInputStream
import java.util.Properties
import scala.collection.JavaConverters._

/** Entry point run on Databricks: reads raw transactions from Snowflake,
  * computes point-in-time-safe features (see Features.scala), writes the
  * result to Delta Lake as the feature store's offline table.
  *
  * Databricks Community Edition has no Jobs scheduling, so this runs as an
  * interactive notebook cell (`FeatureEngineeringJob.run(spark, config)`) or
  * via `spark-submit` from the Databricks CLI -- not as this object's
  * `main`, since Community Edition clusters don't accept submitted JARs
  * either. `main` is kept for local/CI documentation of the intended usage
  * and is exercised by wiring a config in an environment that does support it.
  */
object FeatureEngineeringJob {

  def loadConfig(path: String): Map[String, String] = {
    val props = new Properties()
    val stream = new FileInputStream(path)
    try props.load(stream)
    finally stream.close()
    props.asScala.toMap
  }

  def run(spark: SparkSession, config: Map[String, String]): Unit = {
    val snowflakeOptions = Map(
      "sfURL" -> config("sfURL"),
      "sfUser" -> config("sfUser"),
      "sfPassword" -> config("sfPassword"),
      "sfDatabase" -> config("sfDatabase"),
      "sfSchema" -> config("sfSchema"),
      "sfWarehouse" -> config("sfWarehouse"),
      "sfRole" -> config("sfRole")
    )

    val transactions = spark.read
      .format("net.snowflake.spark.snowflake")
      .options(snowflakeOptions)
      .option("dbtable", config("transactionTable"))
      .load()

    val features = Features.computeVelocityFeatures(transactions)

    features.write
      .format("delta")
      .mode("overwrite")
      .save(config("outputPath"))
  }

  def main(args: Array[String]): Unit = {
    require(args.length == 1, "usage: FeatureEngineeringJob <config.properties>")
    val config = loadConfig(args(0))
    val spark = SparkSession.builder().appName("fraud-feature-engineering").getOrCreate()
    try run(spark, config)
    finally spark.stop()
  }
}
