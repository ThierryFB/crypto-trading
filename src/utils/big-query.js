const { BigQuery } = require('@google-cloud/bigquery')

const bigquery = new BigQuery()

exports.getBitcoinPrices = async ({ date }) => {
  const query = `
SELECT
  DATETIME(timeOpen, 'UTC') as timeOpen,
  DATETIME(timeClose, 'UTC') as timeClose,
  DATETIME(timeHigh, 'UTC') as timeHigh,
  DATETIME(timeLow, 'UTC') as timeLow,
  open,
  high,
  low,
  close
FROM trading.bitcoin_history
WHERE timeOpen < TIMESTAMP(CURRENT_DATE())
ORDER BY timeOpen DESC LIMIT 1000
  `
  const options = {
    query
  }
  const [rows] = await bigquery.query(options)
  return rows
}
