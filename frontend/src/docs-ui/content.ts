import bgSource from "./bg.md?raw";
import deSource from "./de.md?raw";
import enSource from "./en.md?raw";
import frSource from "./fr.md?raw";

import type {
  DocumentationArticle,
  DocumentationLanguage,
  DocumentationSearchResult,
} from "../types/documentation";

const sources: Record<DocumentationLanguage, string> = {
  bg: bgSource,
  en: enSource,
  de: deSource,
  fr: frSource,
};

export const documentationLanguages = [
  { code: "bg", label: "Bulgarian", shortLabel: "BG" },
  { code: "en", label: "English", shortLabel: "EN" },
  { code: "de", label: "German", shortLabel: "DE" },
  { code: "fr", label: "French", shortLabel: "FR" },
] as const;

function readMetadata(block: string): Record<string, string> {
  return block.split("\n").reduce<Record<string, string>>((metadata, line) => {
    const separator = line.indexOf(":");
    if (separator === -1) return metadata;
    const key = line.slice(0, separator).trim();
    const value = line.slice(separator + 1).trim();
    if (key) metadata[key] = value;
    return metadata;
  }, {});
}

function parseArticle(raw: string, language: DocumentationLanguage): DocumentationArticle | null {
  const trimmed = raw.trim();
  if (!trimmed.startsWith("---")) return null;
  const end = trimmed.indexOf("\n---", 3);
  if (end === -1) return null;
  const metadata = readMetadata(trimmed.slice(3, end).trim());
  const content = trimmed.slice(end + 4).trim();
  const slug = metadata.slug;
  const title = metadata.title;
  const category = metadata.category;
  const summary = metadata.summary;
  if (!slug || !title || !category || !summary) return null;
  return {
    slug,
    title,
    category,
    summary,
    keywords: (metadata.keywords ?? "").split(",").map((item) => item.trim()).filter(Boolean),
    related: (metadata.related ?? "").split(",").map((item) => item.trim()).filter(Boolean),
    content,
    headings: content.split("\n").filter((line) => line.startsWith("## ")).map((line) => line.replace(/^##\s+/, "")),
    language,
  };
}

function parseLanguage(source: string, language: DocumentationLanguage): DocumentationArticle[] {
  return source
    .split(/\n---\n(?=slug:)/)
    .map((part, index) => (index === 0 ? part : `---\n${part}`))
    .map((part) => parseArticle(part, language))
    .filter((article): article is DocumentationArticle => article !== null);
}

export const documentationByLanguage = Object.fromEntries(
  documentationLanguages.map(({ code }) => [code, parseLanguage(sources[code], code)]),
) as Record<DocumentationLanguage, DocumentationArticle[]>;

export const fallbackArticles = documentationByLanguage.en;

export function getArticles(language: DocumentationLanguage): DocumentationArticle[] {
  const articles = documentationByLanguage[language];
  return articles.length > 0 ? articles : fallbackArticles;
}

export function getArticle(language: DocumentationLanguage, slug: string): DocumentationArticle {
  const article =
    getArticles(language).find((item) => item.slug === slug) ??
    fallbackArticles.find((item) => item.slug === slug) ??
    fallbackArticles[0];
  return article;
}

export function articleIndex(language: DocumentationLanguage, slug: string): number {
  return getArticles(language).findIndex((article) => article.slug === slug);
}

function normalize(value: string): string {
  return value.toLocaleLowerCase();
}

function excerpt(text: string, query: string): string {
  const plain = text.replace(/[#>*_[\]!`-]/g, " ").replace(/\s+/g, " ").trim();
  const index = normalize(plain).indexOf(normalize(query));
  if (index === -1) return `${plain.slice(0, 140)}${plain.length > 140 ? "..." : ""}`;
  const start = Math.max(0, index - 50);
  const end = Math.min(plain.length, index + query.length + 90);
  return `${start > 0 ? "..." : ""}${plain.slice(start, end)}${end < plain.length ? "..." : ""}`;
}

export function searchDocumentation(
  language: DocumentationLanguage,
  query: string,
): DocumentationSearchResult[] {
  const normalized = normalize(query.trim());
  if (!normalized) return [];
  return getArticles(language)
    .map((article) => {
      const title = normalize(article.title);
      const headings = normalize(article.headings.join(" "));
      const keywords = normalize(article.keywords.join(" "));
      const content = normalize(article.content);
      const score =
        (title.includes(normalized) ? 8 : 0) +
        (headings.includes(normalized) ? 5 : 0) +
        (keywords.includes(normalized) ? 4 : 0) +
        (content.includes(normalized) ? 2 : 0);
      return { article, excerpt: excerpt(article.content, query), score };
    })
    .filter((result) => result.score > 0)
    .sort((first, second) => second.score - first.score || first.article.title.localeCompare(second.article.title));
}
