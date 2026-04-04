const OUTLETS: { name: string; description: string; href: string }[] = [
  { name: "CNBC", description: "Markets, earnings, and business headlines.", href: "https://www.cnbc.com/" },
  { name: "Bloomberg", description: "Global finance and markets coverage.", href: "https://www.bloomberg.com/" },
  {
    name: "Reuters Business",
    description: "International business and breaking news.",
    href: "https://www.reuters.com/business/",
  },
  { name: "Wall Street Journal", description: "US business and economy reporting.", href: "https://www.wsj.com/" },
  { name: "Financial Times", description: "Global markets and economics.", href: "https://www.ft.com/" },
  { name: "MarketWatch", description: "Stocks, quotes, and personal finance.", href: "https://www.marketwatch.com/" },
  { name: "Yahoo Finance", description: "Quotes, news, and market data.", href: "https://finance.yahoo.com/" },
  { name: "Investing.com", description: "Charts, calendars, and multi-asset news.", href: "https://www.investing.com/" },
  { name: "Seeking Alpha", description: "Analysis and crowd-sourced market commentary.", href: "https://seekingalpha.com/" },
  { name: "The Economist", description: "Business, finance, and world affairs.", href: "https://www.economist.com/" },
];

export function BusinessNewsView() {
  return (
    <div className="mx-auto max-w-6xl px-4 pb-24 pt-10 sm:px-6 lg:px-8">
      <header className="mb-10">
        <p className="font-display text-sm font-semibold uppercase tracking-widest text-mint-600">
          Business news
        </p>
        <h1 className="font-display mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
          Market &amp; business sources
        </h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-600">
          Quick links to major business and finance publishers. Opens in a new tab. 24×7 Sherpa is not affiliated
          with these sites; use at your own discretion.
        </p>
      </header>

      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {OUTLETS.map((o) => (
          <li key={o.href}>
            <a
              href={o.href}
              target="_blank"
              rel="noopener noreferrer"
              className="glass block h-full rounded-2xl p-5 transition hover:border-mint-500/40 hover:shadow-md"
            >
              <span className="font-display text-lg font-semibold text-slate-900">{o.name}</span>
              <span className="mt-2 block text-sm text-slate-600">{o.description}</span>
              <span className="mt-3 inline-flex text-xs font-medium text-mint-700">
                Visit →
                <span className="sr-only"> {'('}opens new window{')'}</span>
              </span>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
