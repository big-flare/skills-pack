/**
 * Google Ads Audit Analysis: data export
 * Part of the Big Flare Skills Pack: https://github.com/big-flare/skills-pack
 *
 * READ-ONLY. This script only reads reports from your Google Ads account. It never changes a campaign,
 * budget, bid, keyword or setting: it has no mutate, create, pause or remove calls anywhere.
 *
 * What it does: runs the queries the audit needs and saves the results as ONE file in your Google Drive
 * (named in the log when it finishes). Download that file and give it to Claude.
 *
 * How to run it:
 *   1. In Google Ads: Tools > Bulk actions > Scripts > the + button > New script.
 *   2. Delete the sample code, paste this whole file in, and give the script a name.
 *   3. Click Authorize and allow access (it needs your Google Ads data and permission to create the
 *      one file in your Google Drive).
 *   4. Click Run. When it finishes, open the Logs: the last line links to the file it saved.
 *
 * Running it from a manager (MCC) account? Put the account's ID in CUSTOMER_ID below.
 */

var CONFIG = {
  // The report's date range (YYYY-MM-DD). Leave both empty for the last 90 days up to yesterday.
  START_DATE: '',
  END_DATE: '',
  // Only when running from a manager (MCC) account: the ID of the account to export, e.g. '123-456-7890'.
  CUSTOMER_ID: ''
};

function main() {
  var account = selectAccount();
  var tz = account.getTimeZone();
  var yesterday = Utilities.formatDate(new Date(Date.now() - 86400000), tz, 'yyyy-MM-dd');
  var end = CONFIG.END_DATE || yesterday;
  var start = CONFIG.START_DATE || shiftDays(end, -89);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(start) || !/^\d{4}-\d{2}-\d{2}$/.test(end) || start > end) {
    throw new Error('START_DATE and END_DATE must be YYYY-MM-DD, with START_DATE first.');
  }
  var thisYear = Number(end.slice(0, 4));
  var calendar = { from: (thisYear - 1) + '-01-01', to: end, lastYearEnd: (thisYear - 1) + '-12-31', thisYearStart: thisYear + '-01-01' };

  var bundle = {
    format: 'google-ads-audit-analysis/1',
    meta: {
      account_name: account.getName(),
      customer_id: account.getCustomerId(),
      currency_code: account.getCurrencyCode(),
      time_zone: tz,
      date_from: start,
      date_to: end,
      calendar_from: calendar.from,
      calendar_to: calendar.to,
      exported_at: new Date().toISOString(),
      source: 'google-ads-script'
    },
    datasets: {},
    errors: {}
  };

  var queries = buildQueries(start, end, calendar);
  for (var name in queries) {
    var started = Date.now();
    try {
      bundle.datasets[name] = runQuery(queries[name]);
      Logger.log(name + ': ' + bundle.datasets[name].rows.length + ' rows (' + Math.round((Date.now() - started) / 1000) + 's)');
    } catch (e) {
      bundle.errors[name] = String(e && e.message ? e.message : e);
      Logger.log(name + ': FAILED: ' + bundle.errors[name]);
    }
  }

  var fileName = 'google-ads-audit-data-' + account.getCustomerId() + '-' + start + '-to-' + end + '.json';
  var file = DriveApp.createFile(fileName, JSON.stringify(bundle), MimeType.PLAIN_TEXT);
  Logger.log('Saved ' + fileName + ' to your Google Drive: ' + file.getUrl());
  Logger.log('Download it (File > Download) and give it to Claude.');
}

function selectAccount() {
  if (CONFIG.CUSTOMER_ID && typeof AdsManagerApp !== 'undefined') {
    var id = CONFIG.CUSTOMER_ID.replace(/[^0-9]/g, '');
    var it = AdsManagerApp.accounts().withIds([id]).get();
    if (!it.hasNext()) throw new Error('No account ' + CONFIG.CUSTOMER_ID + ' under this manager account.');
    AdsManagerApp.select(it.next());
  }
  return AdsApp.currentAccount();
}

function shiftDays(iso, days) {
  var d = new Date(iso + 'T12:00:00Z');
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function between(a, b) {
  return "segments.date BETWEEN '" + a + "' AND '" + b + "'";
}

// The queries. references/queries.md lists the same ones for a Google Ads connection; keep them in step.
function buildQueries(start, end, cal) {
  var range = between(start, end);
  var accountMetrics = 'metrics.conversions, metrics.cost_micros, metrics.conversions_value, ' +
    'metrics.conversions_value_by_conversion_date, metrics.search_impression_share, ' +
    'metrics.search_rank_lost_impression_share, metrics.search_budget_lost_impression_share';
  return {
    account_monthly: 'SELECT segments.month, ' + accountMetrics + ' FROM customer WHERE ' + between(cal.from, cal.to),
    account_total_last_year: 'SELECT ' + accountMetrics + ' FROM customer WHERE ' + between(cal.from, cal.lastYearEnd),
    account_total_this_year: 'SELECT ' + accountMetrics + ' FROM customer WHERE ' + between(cal.thisYearStart, cal.to),
    account_total_both: 'SELECT ' + accountMetrics + ' FROM customer WHERE ' + between(cal.from, cal.to),
    account_network_monthly: 'SELECT segments.month, segments.ad_network_type, metrics.impressions FROM campaign WHERE ' + between(cal.from, cal.to),
    campaigns_daily: 'SELECT campaign.id, campaign.name, campaign.advertising_channel_type, segments.date, segments.ad_network_type, ' +
      'metrics.cost_micros, metrics.conversions, metrics.conversions_value FROM campaign WHERE ' + range,
    pmax_shopping_daily: 'SELECT campaign.id, campaign.advertising_channel_type, segments.date, segments.ad_network_type, ' +
      'metrics.cost_micros, metrics.conversions, ' +
      "metrics.conversions_value FROM shopping_performance_view WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX' AND " + range,
    assets: 'SELECT asset_group_asset.field_type, asset_group_asset.source, asset_group_asset.resource_name, asset.id, asset.name, ' +
      'asset.type, asset.text_asset.text, asset.youtube_video_asset.youtube_video_id, asset.youtube_video_asset.youtube_video_title, ' +
      'asset.image_asset.full_size.url, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, ' +
      "metrics.conversions_value FROM asset_group_asset WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX' AND " + range,
    products: 'SELECT campaign.id, campaign.advertising_channel_type, segments.ad_network_type, segments.product_item_id, ' +
      'segments.product_title, segments.product_feed_label, metrics.impressions, metrics.clicks, metrics.cost_micros, ' +
      'metrics.conversions, metrics.conversions_value FROM shopping_performance_view ' +
      "WHERE campaign.advertising_channel_type IN ('PERFORMANCE_MAX', 'SHOPPING') AND " + range,
    product_inventory: 'SELECT shopping_product.item_id, shopping_product.title, shopping_product.status, ' +
      'shopping_product.feed_label, shopping_product.brand, shopping_product.product_type_level1, ' +
      'shopping_product.product_type_level2 FROM shopping_product',
    pmax_search_terms: 'SELECT campaign.id, campaign_search_term_view.search_term, metrics.clicks, metrics.impressions, ' +
      'metrics.conversions, metrics.cost_micros, metrics.conversions_value FROM campaign_search_term_view ' +
      "WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX' AND metrics.conversions > 0 AND " + range,
    search_keywords: 'SELECT campaign.id, campaign.status, ad_group.status, ad_group_criterion.keyword.text, ' +
      'ad_group_criterion.keyword.match_type, ad_group_criterion.status, ad_group_criterion.system_serving_status, ' +
      'ad_group_criterion.primary_status, ad_group_criterion.primary_status_reasons FROM keyword_view ' +
      "WHERE campaign.advertising_channel_type = 'SEARCH' AND ad_group_criterion.negative = FALSE"
  };
}

// Runs one query and returns {fields, rows}: one array of values per row, in the order of the SELECT.
function runQuery(query) {
  var fields = query.replace(/^SELECT\s+/i, '').split(/\s+FROM\s+/i)[0].split(',').map(function (f) { return f.trim(); });
  var paths = fields.map(function (f) { return f.split('.').map(camel); });
  var rows = [];
  var it = AdsApp.search(query);
  while (it.hasNext()) {
    var row = it.next();
    var out = [];
    for (var i = 0; i < paths.length; i++) {
      var v = row;
      for (var j = 0; j < paths[i].length && v !== undefined && v !== null; j++) v = v[paths[i][j]];
      out.push(v === undefined ? null : v);
    }
    rows.push(out);
  }
  return { fields: fields, rows: rows };
}

function camel(s) {
  return s.replace(/_([a-z0-9])/g, function (m, c) { return c.toUpperCase(); });
}
