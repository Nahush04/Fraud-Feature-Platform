package featureeng

import org.apache.spark.sql.Row
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

case class Txn(
    TransactionID: Int,
    TransactionDT: Long,
    TransactionAmt: Double,
    card1: Int,
    P_emaildomain: Option[String]
)

class FeaturesSpec extends AnyFlatSpec with Matchers with SparkSessionTestWrapper {
  import spark.implicits._

  private def byId(rows: Array[Row]): Map[Int, Row] =
    rows.map(r => r.getAs[Int]("TransactionID") -> r).toMap

  "computeVelocityFeatures" should "count only prior transactions within the trailing window, excluding the current row" in {
    val txns = Seq(
      Txn(1, 0L, 10.0, 100, Some("gmail.com")),
      Txn(2, 1800L, 20.0, 100, Some("gmail.com")), // 30 min after #1
      Txn(3, 5000L, 30.0, 100, Some("gmail.com")) // ~53 min after #2, ~83 min after #1
    ).toDF()

    val result = byId(Features.computeVelocityFeatures(txns).collect())

    result(1).getAs[Long]("entity_txn_count_1h") shouldBe 0L
    result(2).getAs[Long]("entity_txn_count_1h") shouldBe 1L // only #1 within 1h before #2
    result(3).getAs[Long]("entity_txn_count_1h") shouldBe 1L // only #2 within 1h before #3 (#1 is ~83min prior, outside)
  }

  it should "never count a transaction at the exact same timestamp as itself" in {
    val txns = Seq(
      Txn(1, 100L, 10.0, 100, None),
      Txn(2, 100L, 15.0, 100, None) // same TransactionDT as #1
    ).toDF()

    val result = byId(Features.computeVelocityFeatures(txns).collect())

    result(1).getAs[Long]("entity_prior_txn_count") shouldBe 0L
    result(2).getAs[Long]("entity_prior_txn_count") shouldBe 0L
  }

  it should "leave entity_amt_zscore null until there are at least two prior transactions" in {
    val txns = Seq(
      Txn(1, 0L, 10.0, 100, None),
      Txn(2, 100L, 12.0, 100, None), // only 1 prior -> still null
      Txn(3, 200L, 14.0, 100, None) // 2 priors -> computable
    ).toDF()

    val result = byId(Features.computeVelocityFeatures(txns).collect())

    result(1).isNullAt(result(1).fieldIndex("entity_amt_zscore")) shouldBe true
    result(2).isNullAt(result(2).fieldIndex("entity_amt_zscore")) shouldBe true
    result(3).isNullAt(result(3).fieldIndex("entity_amt_zscore")) shouldBe false
  }

  it should "compute time since the last transaction for the same entity, null for the first" in {
    val txns = Seq(
      Txn(1, 1000L, 10.0, 100, None),
      Txn(2, 1500L, 20.0, 100, None),
      Txn(3, 9999L, 30.0, 999, None) // different entity -> no predecessor
    ).toDF()

    val result = byId(Features.computeVelocityFeatures(txns).collect())

    result(1).isNullAt(result(1).fieldIndex("entity_time_since_last_txn")) shouldBe true
    result(2).getAs[Long]("entity_time_since_last_txn") shouldBe 500L
    result(3).isNullAt(result(3).fieldIndex("entity_time_since_last_txn")) shouldBe true
  }

  it should "only count email velocity among transactions sharing an email, and leave it null with no email" in {
    val txns = Seq(
      Txn(1, 0L, 10.0, 100, Some("a@x.com")),
      Txn(2, 100L, 10.0, 200, Some("a@x.com")), // different entity, same email
      Txn(3, 200L, 10.0, 300, None) // no email at all
    ).toDF()

    val result = byId(Features.computeVelocityFeatures(txns).collect())

    result(2).getAs[Long]("email_txn_count_24h") shouldBe 1L
    result(3).isNullAt(result(3).fieldIndex("email_txn_count_24h")) shouldBe true
  }
}
