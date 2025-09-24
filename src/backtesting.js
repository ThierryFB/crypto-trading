const { getTimeSeriesFromFile } = require('./utils')
const { getBitcoinPrices } = require('./utils/big-query')
const { getDummyRSI, getExpoWeightedRSI, getWilderRSI } = require('./utils/stats')
const { sellRSI, buyRSI, rsiRebuyThreshold, rsiResellThreshold } = require('./utils/constants')
const FILE_NAME = 'dogecoin-history.csv'
const DATE_SOURCE = 'big-query' // 'file' or 'big-query'
const transactions = []
const enrichedTimeSeries = []
const sellSize = 1000
const buySize = sellSize * 1.5
const startingCash = 100000 // Starting cash
const RSI_METHOD = 'wilder' // 'dummy' or 'expo-weighted'

const getPortfolio = ({ transactions, marketPrice, windowSize }) => {
  // Calculate the portfolio based on transactions
  const portfolio = {
    cash: startingCash,
    position: 0, // Positions by date
    positionValue: 0, // Value of positions
    meanPrice: 0, // Mean price of positions
    pnl: 0, // Total PnL
    realizedPnL: 0, // Realized PnL
    mtm: 0, // Mark-to-market PnL
    minCash: startingCash
  }
  transactions.forEach(transaction => {
    if (transaction.type === 'buy') {
      portfolio.cash -= transaction.price * transaction.quantity
      portfolio.minCash = Math.min(portfolio.minCash, portfolio.cash)
      portfolio.meanPrice = ((portfolio.position * portfolio.meanPrice) + (transaction.price * transaction.quantity)) / (portfolio.position + transaction.quantity)
      portfolio.position += transaction.quantity
      portfolio.realizedPnL += (-transaction.price + portfolio.meanPrice) * transaction.quantity
    } else if (transaction.type === 'sell' && portfolio.position >= transaction.quantity) {
      portfolio.cash += transaction.price * transaction.quantity
      portfolio.position -= transaction.quantity
      portfolio.realizedPnL += (transaction.price - portfolio.meanPrice) * transaction.quantity
    }
    portfolio.positionValue = (portfolio.position * transaction.price).toFixed(2)
    // console.debug('portfolio: ', portfolio)
  })
  portfolio.marketPrice = marketPrice
  portfolio.mtm = ((portfolio.marketPrice - portfolio.meanPrice) * portfolio.position).toFixed(2)
  portfolio.pnl = portfolio.realizedPnL + +portfolio.mtm
  portfolio.returnOnCapital = ((portfolio.realizedPnL / (startingCash - portfolio.minCash)) * 100 * 365 / windowSize).toFixed(2)
  return portfolio
}

const getTransaction = ({ timeSeries }) => {
  if ((timeSeries[0].highRsi >= sellRSI && timeSeries[1].rsi < sellRSI) || (timeSeries[0].highRsi >= sellRSI && (timeSeries[0].highRsi - timeSeries[1].rsi) > rsiResellThreshold)) {
    if (timeSeries[1].sellTarget > timeSeries[0].high || timeSeries[1].sellTarget < timeSeries[0].low) {
      console.warn('sellTarget is wrong, this should not happen')
      // console.debug('timeSeries: ', timeSeries.slice(0, 2))
    }
    return {
      type: 'sell',
      price: timeSeries[1].sellTarget,
      date: timeSeries[0].date,
      quantity: sellSize / timeSeries[1].sellTarget,
      highRsi: timeSeries[0].highRsi,
      previousRsi: timeSeries[1].rsi
    }
  }
  if ((timeSeries[0].lowRsi < buyRSI && timeSeries[1].rsi >= buyRSI) || ((timeSeries[0].lowRsi < buyRSI && (timeSeries[1].rsi - timeSeries[0].lowRsi) > rsiRebuyThreshold))) {
    if (timeSeries[1].buyTarget < timeSeries[0].low || timeSeries[1].buyTarget > timeSeries[0].high) {
      console.warn('buyTarget is wrong, this should not happen')
      // console.debug('timeSeries: ', timeSeries.slice(0, 2))
    }
    return {
      type: 'buy',
      price: timeSeries[1].buyTarget,
      date: timeSeries[0].date,
      quantity: buySize / timeSeries[1].buyTarget,
      lowRsi: timeSeries[0].lowRsi,
      previousRsi: timeSeries[1].rsi
    }
  }
}

const runBacktesting = async () => {
  try {
    let rsi, buyTarget, sellTarget, lowRsi, highRsi, records, previousGainAverage, previousLossAverage
    if (DATE_SOURCE === 'big-query') {
      records = await getBitcoinPrices({ date: '2023-01-01' })
    } else {
      records = await getTimeSeriesFromFile({ fileName: FILE_NAME })
    }
    // Process the records
    for (let i = records.length - 15; i >= 0; i--) {
      const timeSeries = records.slice(i, i + 15)
      const timeSeriesItem = {
        date: records[i].timeOpen,
        price: parseFloat(records[i].close),
        low: parseFloat(records[i].low),
        high: parseFloat(records[i].high)
      }
      switch (RSI_METHOD) {
        case 'dummy':
          ;({ rsi, buyTarget, sellTarget } = getDummyRSI({ timeSeries }))
          ;({ rsi: lowRsi } = getDummyRSI({ timeSeries: [{ ...timeSeries[0], close: timeSeries[0].low }, ...timeSeries.slice(1)] }))
          ;({ rsi: highRsi } = getDummyRSI({ timeSeries: [{ ...timeSeries[0], close: timeSeries[0].high }, ...timeSeries.slice(1)] }))
          break
        case 'expo-weighted':
          ;({ rsi, buyTarget, sellTarget } = getExpoWeightedRSI({ timeSeries }))
          ;({ rsi: lowRsi } = getExpoWeightedRSI({ timeSeries: [{ ...timeSeries[0], close: timeSeries[0].low }, ...timeSeries.slice(1)] }))
          ;({ rsi: highRsi } = getExpoWeightedRSI({ timeSeries: [{ ...timeSeries[0], close: timeSeries[0].high }, ...timeSeries.slice(1)] }))
          break
        case 'wilder':
          ;({ rsi, buyTarget, sellTarget, averageGain: previousGainAverage, averageLoss: previousLossAverage } = getWilderRSI({ timeSeries, previousGainAverage, previousLossAverage }))
          ;({ rsi: lowRsi } = getWilderRSI({ timeSeries: [{ ...timeSeries[0], close: timeSeries[0].low }, ...timeSeries.slice(1)], previousGainAverage, previousLossAverage }))
          ;({ rsi: highRsi } = getWilderRSI({ timeSeries: [{ ...timeSeries[0], close: timeSeries[0].high }, ...timeSeries.slice(1)], previousGainAverage, previousLossAverage }))
          break
        default:
          throw new Error('Unknown RSI method')
      }
      timeSeriesItem.rsi = rsi
      timeSeriesItem.buyTarget = buyTarget
      timeSeriesItem.sellTarget = sellTarget
      timeSeriesItem.highRsi = highRsi
      timeSeriesItem.lowRsi = lowRsi
      // console.log('timeSeriesItem: ', timeSeriesItem)
      enrichedTimeSeries.unshift(timeSeriesItem)
      if (enrichedTimeSeries.length < 2) continue
      const transaction = getTransaction({
        timeSeries: enrichedTimeSeries
      })
      if (transaction) transactions.push(transaction)
      // if (transaction) console.debug('transaction: ', transaction)
    }
    const portfolio = getPortfolio({
      transactions,
      marketPrice: enrichedTimeSeries[0].price,
      windowSize: enrichedTimeSeries.length
    })
    console.info('window size: ', enrichedTimeSeries.length)
    console.info('Time Series: ', enrichedTimeSeries.splice(0, 5))
    console.info('Buy Target: ', buyTarget)
    console.info('Sell Target: ', sellTarget)
    console.log('Final Portfolio: ', portfolio)
    console.log('# transactions: ', transactions.length)
    // console.log('transactions: ', transactions)
  } catch (error) {
    console.error(error)
  }
}

(async () => {
  try {
    await runBacktesting()
  } catch (error) {
    console.error(error)
  }
})()
