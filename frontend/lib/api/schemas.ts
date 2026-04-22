import { z } from "zod";

export const stockQuoteAttrSchema = z.object({
  ticker: z.string(),
  "Quote Price": z.number().nullable().optional(),
  "Previous Close": z.number().nullable().optional(),
  Open: z.number().nullable().optional(),
  Volume: z.number().nullable().optional(),
  change_percent: z.number().nullable().optional(),
  company: z.string().optional(),
  data_source: z.string().optional(),
});

export type StockQuoteAttr = z.infer<typeof stockQuoteAttrSchema>;

export const ohlcAttrSchema = z.object({
  ticker: z.string(),
  Open: z.number().nullable(),
  High: z.number().nullable(),
  Low: z.number().nullable(),
  Close: z.number().nullable(),
  "Adj Close": z.number().nullable().optional(),
  Volume: z.number().nullable().optional(),
  data_source: z.string().optional(),
});

export const indicatorsSchema = z.object({
  MA5: z.number().nullable().optional(),
  MA20: z.number().nullable().optional(),
  volatility_annual_pct: z.number().nullable().optional(),
  week52_high: z.number().nullable().optional(),
  week52_low: z.number().nullable().optional(),
  days_high: z.number().nullable().optional(),
  days_low: z.number().nullable().optional(),
});

export type Indicators = z.infer<typeof indicatorsSchema>;

export const newsAttrSchema = z.object({
  title: z.string().nullable().optional(),
  summary: z.string().nullable().optional(),
  link: z.string().nullable().optional(),
  published: z.string().nullable().optional(),
  source: z.string().nullable().optional(),
  region: z.string().nullable().optional(),
  sentiment: z.enum(["positive", "negative", "neutral"]).default("neutral"),
  impact_score: z.number().default(0),
  related_stock: z.string().nullable().optional(),
  data_source: z.string().optional(),
});

export type NewsAttr = z.infer<typeof newsAttrSchema>;

export const eventSchema = z.object({
  time_object: z.record(z.any()),
  event_type: z.string(),
  attribute: z.record(z.any()),
});

export const stockResponseSchema = z.object({
  data_source: z.string().optional(),
  dataset_type: z.string().optional(),
  dataset_id: z.string().optional(),
  cached: z.boolean().optional(),
  events: z.array(eventSchema),
  ohlc_data_points: z.number().optional(),
});

export const newsResponseSchema = z.object({
  events: z.array(eventSchema),
  total: z.number().optional(),
  cached: z.boolean().optional(),
});

export const analysisResponseSchema = z.object({
  stock: z.string(),
  period: z.string().nullable().optional(),
  indicators: indicatorsSchema.nullable(),
  ohlc_series: z.array(
    z.object({
      date: z.string(),
      Open: z.number().nullable(),
      High: z.number().nullable(),
      Low: z.number().nullable(),
      Close: z.number().nullable(),
      Volume: z.number().nullable().optional(),
    })
  ),
  data_points: z.number(),
  cached: z.boolean().optional(),
});

export type AnalysisResponse = z.infer<typeof analysisResponseSchema>;

export const reportResponseSchema = z.object({
  stock: z.string(),
  generated_at: z.string(),
  model: z.string(),
  summary: z.string(),
  key_drivers: z.array(z.string()),
  risks: z.array(z.string()),
  overall_sentiment: z.enum(["positive", "negative", "neutral"]),
  articles_considered: z.number(),
  cached: z.boolean().optional(),
});

export type ReportResponse = z.infer<typeof reportResponseSchema>;
