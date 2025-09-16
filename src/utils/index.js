const fs = require('fs/promises')
const { parse } = require('csv-parse/sync')

exports.getTimeSeriesFromFile = async ({ fileName }) => {
  const data = await fs.readFile(`./data/${fileName}`, 'utf8')
  // Parse the CSV data
  const records = parse(data, {
    columns: true,
    skip_empty_lines: true,
    delimiter: ';'
  })
  return records
}
