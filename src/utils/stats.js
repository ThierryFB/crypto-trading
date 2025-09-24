const { sellRSI, buyRSI, rsiRebuyThreshold, rsiResellThreshold } = require('./constants')

exports.getDummyRSI = ({ timeSeries }) => {
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
  return { rsi, buyTarget, sellTarget, averageGain, averageLoss }
}

exports.getExpoWeightedRSI = ({ timeSeries, alpha = 0.2 }) => {
  if (!timeSeries || timeSeries.length < 2) return 0
  let averageGain = Math.max(0, timeSeries[timeSeries.length - 2].close - timeSeries[timeSeries.length - 1].close)
  let averageLoss = -Math.min(0, timeSeries[timeSeries.length - 2].close - timeSeries[timeSeries.length - 1].close)
  for (let i = timeSeries.length - 2; i > 0; i--) {
    const diff = timeSeries[i - 1].close - timeSeries[i].close
    // if (isNaN(diff)) continue // Skip NaN values
    if (diff > 0) {
      averageGain = alpha * diff + (1 - alpha) * averageGain
      averageLoss = (1 - alpha) * averageLoss
    } else {
      averageGain = (1 - alpha) * averageGain
      averageLoss = alpha * -diff + (1 - alpha) * averageLoss
    }
  }
  if (averageLoss === 0) return 100
  const rs = averageGain / averageLoss
  const rsi = 100 - 100 / (1 + rs)
  const targetSellRSI = rsi > sellRSI ? sellRSI + rsiResellThreshold : sellRSI
  const targetBuyRSI = rsi < buyRSI ? buyRSI - rsiRebuyThreshold : buyRSI
  const targetBuyRS = targetBuyRSI / (100 - targetBuyRSI)
  const targetSellRS = targetSellRSI / (100 - targetSellRSI)
  const newAverageGainAfterLoss = (1 - alpha) * averageGain
  const newAverageLossAfterGain = (1 - alpha) * averageLoss
  const targetAverageLoss = newAverageGainAfterLoss / targetBuyRS
  const targetAverageGain = newAverageLossAfterGain * targetSellRS
  const targetLoss = Math.max(0, (targetAverageLoss - (1 - alpha) * averageLoss) / alpha)
  const targetGain = Math.max(0, (targetAverageGain - (1 - alpha) * averageGain) / alpha)
  const buyTarget = +(+timeSeries[0].close - targetLoss).toFixed(2)
  const sellTarget = +(+timeSeries[0].close + targetGain).toFixed(2)
  return { rsi, buyTarget, sellTarget }
}

exports.getWilderRSI = ({ timeSeries, previousGainAverage, previousLossAverage }) => {
  let rsi, averageGain, averageLoss
  if (!timeSeries || timeSeries.length < 2) return 0
  if (previousGainAverage === undefined || previousLossAverage === undefined) {
    ;({ rsi, averageGain, averageLoss } = this.getDummyRSI({ timeSeries }))
  } else {
    const diff = timeSeries[0].close - timeSeries[1].close
    // if (isNaN(diff)) continue // Skip NaN values
    if (diff > 0) {
      averageGain = (diff + previousGainAverage * 13) / 14
      averageLoss = (previousLossAverage * 13) / 14
    } else {
      averageGain = (previousGainAverage * 13) / 14
      averageLoss = (-diff + previousLossAverage * 13) / 14
    }
    const rs = averageGain / averageLoss
    rsi = 100 - 100 / (1 + rs)
  }
  const targetSellRSI = rsi > sellRSI ? sellRSI + rsiResellThreshold : sellRSI
  const targetBuyRSI = rsi < buyRSI ? buyRSI - rsiRebuyThreshold : buyRSI
  const targetBuyRS = targetBuyRSI / (100 - targetBuyRSI)
  const targetSellRS = targetSellRSI / (100 - targetSellRSI)
  const newAverageGainAfterLoss = (averageGain * 13) / 14
  const newAverageLossAfterGain = (averageLoss * 13) / 14
  const targetAverageLoss = newAverageGainAfterLoss / targetBuyRS
  const targetAverageGain = newAverageLossAfterGain * targetSellRS
  const targetLoss = Math.max(0, (targetAverageLoss * 14 - averageLoss * 13))
  const targetGain = Math.max(0, (targetAverageGain * 14 - averageGain * 13))
  const buyTarget = +(+timeSeries[0].close - targetLoss).toFixed(2)
  const sellTarget = +(+timeSeries[0].close + targetGain).toFixed(2)
  if (timeSeries[0].timeOpen === '2025-09-23T00:00:00') {
    console.debug('timeSeries: ', timeSeries)
    console.debug('averageGain: ', averageGain)
    console.debug('averageLoss: ', averageLoss)
    console.debug('rsi: ', rsi)
    console.debug('targetBuyRS: ', targetBuyRS)
    console.debug('targetSellRS: ', targetSellRS)
    console.debug('newAverageGainAfterLoss: ', newAverageGainAfterLoss)
    console.debug('newAverageLossAfterGain: ', newAverageLossAfterGain)
    console.debug('targetAverageLoss: ', targetAverageLoss)
    console.debug('targetAverageGain: ', targetAverageGain)
    console.debug('targetLoss: ', targetLoss)
    console.debug('targetGain: ', targetGain)
    console.debug('buyTarget: ', buyTarget)
  }
  return { rsi, buyTarget, sellTarget }
}
