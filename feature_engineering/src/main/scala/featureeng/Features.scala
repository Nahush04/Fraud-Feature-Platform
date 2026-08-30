package featureeng

import org.apache.spark.sql.DataFrame
import org.apache.spark.sql.expressions.{Window, WindowSpec}
import org.apache.spark.sql.functions._

/** Point-in-time-safe feature engineering for IEEE-CIS transactions.
  *
  * IEEE-CIS has no true customer/account ID, so `card1` is used as a proxy
  * entity, following common practice for this dataset -- a real deployment
  * would use an actual account or card-token identifier.
  *
  * Every window below uses a RANGE frame with an upper bound of -1, in
  * `TransactionDT` units (seconds). A RANGE frame's boundary is evaluated by
  * value distance from the current row, not row position, so a row sharing
  * the current row's exact timestamp has offset 0 and is excluded by the -1
  * upper bound regardless of physical sort order among ties. That is what
  * makes these features safe against leakage: a feature value for
  * transaction T can only reflect transactions strictly before T.
  *
  * Spark requires a RANGE frame with a numeric offset boundary to have
  * exactly one ORDER BY column, so the range-frame windows here order by
  * `TransactionDT` alone. `entity_time_since_last_txn` instead uses a ROW
  * frame (`lag`), which needs `TransactionID` as a tiebreaker for
  * deterministic ordering among same-second transactions -- documented as a
  * known limitation: a same-second predecessor is possible for that one
  * feature (see docs/decisions.md).
  */
object Features {

  private val EntityCol = "card1"
  private val TimeCol = "TransactionDT"
  private val IdCol = "TransactionID"
  private val AmountCol = "TransactionAmt"
  private val EmailCol = "P_emaildomain"

  private val OneHourSeconds = 3600L
  private val OneDaySeconds = 86400L

  def computeVelocityFeatures(transactions: DataFrame): DataFrame = {
    val entityRangeOrder: WindowSpec = Window.partitionBy(EntityCol).orderBy(TimeCol)
    val entityRowOrder: WindowSpec = Window.partitionBy(EntityCol).orderBy(TimeCol, IdCol)
    val emailRangeOrder: WindowSpec = Window.partitionBy(EmailCol).orderBy(TimeCol)

    val entityTrailing1h = entityRangeOrder.rangeBetween(-OneHourSeconds, -1L)
    val entityTrailing24h = entityRangeOrder.rangeBetween(-OneDaySeconds, -1L)
    val entityAllPrior = entityRangeOrder.rangeBetween(Window.unboundedPreceding, -1L)
    val emailTrailing24h = emailRangeOrder.rangeBetween(-OneDaySeconds, -1L)

    transactions
      .withColumn("entity_txn_count_1h", count(lit(1)).over(entityTrailing1h))
      .withColumn("entity_txn_count_24h", count(lit(1)).over(entityTrailing24h))
      .withColumn("entity_prior_txn_count", count(lit(1)).over(entityAllPrior))
      .withColumn("entity_prior_amt_mean", avg(col(AmountCol)).over(entityAllPrior))
      .withColumn("entity_prior_amt_stddev", stddev_samp(col(AmountCol)).over(entityAllPrior))
      .withColumn(
        "entity_amt_zscore",
        when(
          col("entity_prior_txn_count") < 2 ||
            col("entity_prior_amt_stddev").isNull ||
            col("entity_prior_amt_stddev") === 0.0,
          lit(null).cast("double")
        ).otherwise((col(AmountCol) - col("entity_prior_amt_mean")) / col("entity_prior_amt_stddev"))
      )
      .withColumn("entity_prev_txn_time", lag(col(TimeCol), 1).over(entityRowOrder))
      .withColumn(
        "entity_time_since_last_txn",
        when(col("entity_prev_txn_time").isNull, lit(null).cast("long"))
          .otherwise(col(TimeCol) - col("entity_prev_txn_time"))
      )
      .withColumn(
        "email_txn_count_24h",
        when(col(EmailCol).isNull, lit(null).cast("long")).otherwise(count(lit(1)).over(emailTrailing24h))
      )
      .drop("entity_prev_txn_time")
  }
}
