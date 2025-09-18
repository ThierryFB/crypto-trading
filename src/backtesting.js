const { getTimeSeriesFromFile } = require('./utils')
const { getBitcoinPrices } = require('./utils/big-query')
const FILE_NAME = 'dogecoin-history.csv'
const DATE_SOURCE = 'big-query' // 'file' or 'big-query'
const transactions = []
const enrichedTimeSeries = []
const sellSize = 2500
const buySize = sellSize * 2
const startingCash = 100000 // Starting cash
const sellRSI = 70 // RSI threshold for selling
const buyRSI = 30 // RSI threshold for buying
const rsiRebuyThreshold = 5 // RSI threshold for re-buying after selling
const rsiResellThreshold = 5 // RSI threshold for re-selling after buying

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

const getRSI = ({ timeSeries }) => {
  // Calculate RSI based on the lastDays data
  if (!timeSeries || timeSeries.length < 2) return 0
  let gains = 0
  let losses = 0
  let countGains = 0
  let countLosses = 0
  let oldLoss = 0
  let oldGain = 0
  for (let i = 1; i < timeSeries.length; i++) {
    const diff = timeSeries[i - 1].close - timeSeries[i].close
    // if (isNaN(diff)) continue // Skip NaN values
    if (diff > 0) {
      gains += diff
      if (i === timeSeries.length - 1) oldGain = diff
      countGains++
    } else {
      losses -= diff
      if (i === timeSeries.length - 1) oldLoss = -diff
      countLosses++
    }
  }
  const size = timeSeries.length - 1
  const averageGain = countGains > 0 ? gains / size : 0
  const averageLoss = countLosses > 0 ? losses / size : 0
  if (averageLoss === 0) return 100

  const rs = averageGain / averageLoss
  const rsi = 100 - 100 / (1 + rs)
  const averageGainWithoutOld = countGains > 0 ? (gains - oldGain) / (size - 1) : 0
  const averageLossWithoutOld = countLosses > 0 ? (losses - oldLoss) / (size - 1) : 0
  const targetSellRSI = rsi > sellRSI ? sellRSI + rsiResellThreshold : sellRSI
  const targetBuyRSI = rsi < buyRSI ? buyRSI - rsiRebuyThreshold : buyRSI
  const targetLoss = Math.max(0, averageGainWithoutOld * (size - 1) * targetSellRSI / targetBuyRSI - (averageLossWithoutOld * (size - 1)))
  const targetGain = Math.max(0, averageLossWithoutOld * (size - 1) * targetSellRSI / targetBuyRSI - (averageGainWithoutOld * (size - 1)))
  const buyTarget = +(+timeSeries[0].close - targetLoss).toFixed(2)
  const sellTarget = +(+timeSeries[0].close + targetGain).toFixed(2)
  return { rsi, buyTarget, sellTarget }
}

const getTransaction = ({ timeSeries }) => {
  if ((timeSeries[0].highRsi >= sellRSI && timeSeries[1].rsi < sellRSI) || (timeSeries[0].highRsi >= sellRSI && (timeSeries[0].highRsi - timeSeries[1].rsi) > rsiResellThreshold)) {
    if (timeSeries[1].sellTarget > timeSeries[0].high || timeSeries[1].sellTarget < timeSeries[0].low) {
      console.warn('sellTarget is wrong, this should not happen')
      console.debug('timeSeries: ', timeSeries.slice(0, 2))
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
      console.debug('timeSeries: ', timeSeries.slice(0, 2))
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
    let rsi, buyTarget, sellTarget, lowRsi, highRsi, records
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
      ;({ rsi, buyTarget, sellTarget, highRsi, lowRsi } = getRSI({ timeSeries }))
      ;({ rsi: lowRsi } = getRSI({ timeSeries: [{ ...timeSeries[0], close: timeSeries[0].low }, ...timeSeries.slice(1)] }))
      ;({ rsi: highRsi } = getRSI({ timeSeries: [{ ...timeSeries[0], close: timeSeries[0].high }, ...timeSeries.slice(1)] }))
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
