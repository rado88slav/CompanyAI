export type DocumentationLanguage = "bg" | "en" | "de" | "fr";

export interface DocumentationArticle {
  slug: string;
  title: string;
  category: string;
  summary: string;
  keywords: string[];
  related: string[];
  content: string;
  headings: string[];
  language: DocumentationLanguage;
}

export interface DocumentationSearchResult {
  article: DocumentationArticle;
  excerpt: string;
  score: number;
}
