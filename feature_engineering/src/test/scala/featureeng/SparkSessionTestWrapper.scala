package featureeng

import org.apache.spark.sql.SparkSession
import org.scalatest.{BeforeAndAfterAll, Suite}

trait SparkSessionTestWrapper extends BeforeAndAfterAll { self: Suite =>
  lazy val spark: SparkSession = SparkSession
    .builder()
    .master("local[2]")
    .appName("featureeng-test")
    .config("spark.sql.shuffle.partitions", "2")
    .config("spark.ui.enabled", "false")
    .getOrCreate()

  override def afterAll(): Unit = {
    spark.stop()
    super.afterAll()
  }
}
