// The "drama timeline": major news days shown as hollow-square markers on the equity chart.
import type { Ticker } from '../api/backtests'

export interface StockEvent {
  date: string
  title: string
  detail: string
}

export const EVENTS: Record<Ticker, StockEvent[]> = {
  META: [
    {
      date: '2018-03-19',
      title: 'Cambridge Analytica',
      detail: 'First trading day after reports that a consultancy had harvested data from millions of Facebook users. Shares slid as regulators and lawmakers piled in.',
    },
    {
      date: '2018-07-26',
      title: 'Record one-day drop',
      detail: 'After slowing user growth in its second-quarter results, Facebook lost more market value in a single day than any U.S. company had before.',
    },
    {
      date: '2021-10-28',
      title: 'Rebrand to Meta',
      detail: 'Facebook renamed itself Meta Platforms and bet its future on the metaverse.',
    },
    {
      date: '2022-02-03',
      title: 'Feb 2022 drop',
      detail: 'The first-ever drop in daily users and heavy metaverse spending sent the stock down about a quarter in one day.',
    },
    {
      date: '2023-02-02',
      title: 'Year of efficiency',
      detail: 'Meta promised a "year of efficiency" with layoffs and cost cuts, and the stock jumped the next day, starting its comeback.',
    },
  ],
  PLTR: [
    {
      date: '2020-09-30',
      title: 'Direct listing',
      detail: 'Palantir started trading on the NYSE through a direct listing instead of a traditional IPO.',
    },
    {
      date: '2023-05-09',
      title: 'AI platform rally',
      detail: 'Strong first-quarter results and excitement about its new AI Platform (AIP) sent shares sharply higher.',
    },
    {
      date: '2024-09-23',
      title: 'Joins the S&P 500',
      detail: 'Palantir was added to the S&P 500, so index funds had to buy the stock.',
    },
    {
      date: '2024-11-26',
      title: 'Moves to Nasdaq',
      detail: 'Palantir switched its listing from the NYSE to the Nasdaq.',
    },
  ],
}
