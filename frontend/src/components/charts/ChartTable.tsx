import styles from './ChartTable.module.css'

// Every value a chart shows, as a table: for keyboard and screen-reader users, and for the lighter
// series colours that fall below 3:1 contrast on the light surface. Collapsed by default.
export function ChartTable({
  caption,
  columns,
  rows,
}: {
  caption: string
  columns: string[]
  rows: string[][]
}) {
  return (
    <details className={styles.details}>
      <summary className={styles.summary}>Show as table</summary>
      <div className={styles.scroll}>
        <table className={styles.table}>
          <caption className={styles.caption}>{caption}</caption>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column} scope="col">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(([first, ...rest], index) => (
              <tr key={index}>
                <th scope="row">{first}</th>
                {rest.map((cell, cellIndex) => (
                  <td key={cellIndex}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
