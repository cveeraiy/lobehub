export class Sitemap {
  async getIndex() {
    return `<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" />`;
  }
}
