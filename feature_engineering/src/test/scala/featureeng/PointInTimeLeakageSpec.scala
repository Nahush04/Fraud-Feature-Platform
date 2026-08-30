package featureeng

import org.apache.spark.sql.Row
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

/** The load-bearing correctness test for this whole milestone: every feature
  * value computed for a transaction must be identical whether or not future
  * transactions exist in the input. If this fails, the feature store leaks
  * future information into training data, which would invalidate every
  * downstream model metric.
  */
class PointInTimeLeakageSpec extends AnyFlatSpec with Matchers with SparkSessionTestWrapper {
  import spark.implicits._

  private val entity = 100
  private val withoutFuture = Seq(
    Txn(1, 0L, 10.0, entity, Some("a@x.com")),
    Txn(2, 1800L, 12.0, entity, Some("a@x.com")),
    Txn(3, 5000L, 14.0, entity, Some("a@x.com"))
  )
  private val futureRow = Txn(4, 200000L, 999.0, entity, Some("a@x.com")) // far in the future

  private def rowsById(txns: Seq[Txn]): Map[Int, Row] =
    Features.computeVelocityFeatures(txns.toDF()).collect().map(r => r.getAs[Int]("TransactionID") -> r).toMap

  "features for existing transactions" should "be unchanged when a future transaction is added to the input" in {
    val before = rowsById(withoutFuture)
    val after = rowsById(withoutFuture :+ futureRow)

    val featureCols = Seq(
      "entity_txn_count_1h",
      "entity_txn_count_24h",
      "entity_prior_txn_count",
      "entity_amt_zscore",
      "entity_time_since_last_txn",
      "email_txn_count_24h"
    )

    for (id <- Seq(1, 2, 3); col <- featureCols) {
      val b = before(id)
      val a = after(id)
      val bIdx = b.fieldIndex(col)
      val aIdx = a.fieldIndex(col)
      withClue(s"TransactionID=$id column=$col: ") {
        (b.isNullAt(bIdx), a.isNullAt(aIdx)) match {
          case (true, true)   => succeed
          case (false, false) => b.get(bIdx) shouldBe a.get(aIdx)
          case _              => fail(s"nullness differs: before=${b.get(bIdx)} after=${a.get(aIdx)}")
        }
      }
    }
  }

  it should "still let the new transaction see everything before it (features aren't just frozen)" in {
    val after = rowsById(withoutFuture :+ futureRow)
    after(4).getAs[Long]("entity_prior_txn_count") shouldBe 3L
  }
}
