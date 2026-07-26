import { useEffect, useMemo, useState } from "react";
import type { ReactElement } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  articleIndex,
  documentationLanguages,
  getArticle,
  getArticles,
  searchDocumentation,
} from "../docs-ui/content";
import type { DocumentationArticle, DocumentationLanguage } from "../types/documentation";

const storageKey = "companyai.docsLanguage";

function readSavedLanguage(): DocumentationLanguage {
  const saved = sessionStorage.getItem(storageKey);
  return saved === "bg" || saved === "en" || saved === "de" || saved === "fr" ? saved : "en";
}

function slugify(value: string): string {
  return value.toLocaleLowerCase().replace(/[^a-z0-9а-яёäöüßéèêàçîïôùû]+/gi, "-").replace(/^-|-$/g, "");
}

function highlight(value: string, query: string) {
  if (!query.trim()) return value;
  const index = value.toLocaleLowerCase().indexOf(query.trim().toLocaleLowerCase());
  if (index === -1) return value;
  return (
    <>
      {value.slice(0, index)}
      <mark>{value.slice(index, index + query.length)}</mark>
      {value.slice(index + query.length)}
    </>
  );
}

function parseInline(value: string) {
  const parts = value.split(/(`[^`]+`)/g);
  return parts.map((part, index) => (
    part.startsWith("`") && part.endsWith("`")
      ? <code key={`${part}-${index}`}>{part.slice(1, -1)}</code>
      : <span key={`${part}-${index}`}>{part}</span>
  ));
}

function admonitionType(line: string) {
  const match = line.match(/^>\s+\[!(INFO|WARNING|TIP|NOTE)\]\s*(.*)$/);
  if (!match) return null;
  return { type: match[1].toLocaleLowerCase(), rest: match[2] };
}

function MarkdownArticle({ article }: { article: DocumentationArticle }) {
  const blocks: ReactElement[] = [];
  const lines = article.content.split("\n");
  let list: string[] = [];
  let code: string[] = [];
  let inCode = false;

  function flushList() {
    if (list.length > 0) {
      blocks.push(<ul key={`list-${blocks.length}`}>{list.map((item) => <li key={item}>{parseInline(item.replace(/^\d+\.\s+|^-\s+/, ""))}</li>)}</ul>);
      list = [];
    }
  }

  function flushCode() {
    if (code.length > 0) {
      blocks.push(<pre key={`code-${blocks.length}`}><code>{code.join("\n")}</code></pre>);
      code = [];
    }
  }

  for (const line of lines) {
    if (line.startsWith("```")) {
      if (inCode) flushCode();
      inCode = !inCode;
      continue;
    }
    if (inCode) {
      code.push(line);
      continue;
    }
    if (!line.trim()) {
      flushList();
      continue;
    }
    const admonition = admonitionType(line);
    if (admonition) {
      flushList();
      blocks.push(
        <aside className={`docs-admonition docs-admonition--${admonition.type}`} key={`admonition-${blocks.length}`}>
          <strong>{admonition.type}</strong>
          {admonition.rest && <p>{parseInline(admonition.rest)}</p>}
        </aside>,
      );
      continue;
    }
    if (line.startsWith("# ")) {
      flushList();
      continue;
    }
    if (line.startsWith("## ")) {
      flushList();
      const title = line.slice(3);
      blocks.push(<h2 id={slugify(title)} key={`h2-${title}`}>{title}</h2>);
      continue;
    }
    if (/^(\d+\.|-)\s+/.test(line)) {
      list.push(line);
      continue;
    }
    flushList();
    blocks.push(<p key={`p-${blocks.length}`}>{parseInline(line)}</p>);
  }
  flushList();
  flushCode();
  return <div className="docs-article__body">{blocks}</div>;
}

export function DocumentationCenterPage() {
  const params = useParams();
  const navigate = useNavigate();
  const [language, setLanguage] = useState<DocumentationLanguage>(() => readSavedLanguage());
  const [query, setQuery] = useState("");
  const [copied, setCopied] = useState(false);
  const [progress, setProgress] = useState(0);

  const articles = getArticles(language);
  const slug = params.slug ?? articles[0].slug;
  const article = getArticle(language, slug);
  const index = articleIndex(language, article.slug);
  const previous = index > 0 ? articles[index - 1] : null;
  const next = index >= 0 && index < articles.length - 1 ? articles[index + 1] : null;
  const results = useMemo(() => searchDocumentation(language, query), [language, query]);
  const categories = useMemo(() => {
    return articles.reduce<Record<string, DocumentationArticle[]>>((groups, item) => {
      groups[item.category] = groups[item.category] ?? [];
      groups[item.category].push(item);
      return groups;
    }, {});
  }, [articles]);

  useEffect(() => {
    sessionStorage.setItem(storageKey, language);
  }, [language]);

  useEffect(() => {
    function updateProgress() {
      const scrollable = document.documentElement.scrollHeight - window.innerHeight;
      setProgress(scrollable <= 0 ? 0 : Math.min(100, Math.round((window.scrollY / scrollable) * 100)));
    }
    updateProgress();
    window.addEventListener("scroll", updateProgress, { passive: true });
    return () => window.removeEventListener("scroll", updateProgress);
  }, [article.slug]);

  function changeLanguage(value: DocumentationLanguage) {
    setLanguage(value);
    if (!getArticles(value).some((item) => item.slug === article.slug)) {
      navigate("/documentation/getting-started");
    }
  }

  async function copyLink() {
    const path = `/documentation/${article.slug}`;
    try {
      await navigator.clipboard.writeText(`${window.location.origin}${path}`);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }

  return (
    <section className="page docs-center" aria-labelledby="documentation-title">
      <div className="docs-progress" style={{ width: `${progress}%` }} aria-hidden="true" />
      <div className="overview-hero docs-hero">
        <div>
          <span className="eyebrow">Documentation</span>
          <h1 id="documentation-title">Learn CompanyAI without leaving the dashboard.</h1>
          <p>Searchable multilingual product guidance for the operational console.</p>
        </div>
        <label className="docs-language">
          <span>Language</span>
          <select value={language} onChange={(event) => changeLanguage(event.target.value as DocumentationLanguage)}>
            {documentationLanguages.map((item) => (
              <option value={item.code} key={item.code}>{item.shortLabel} · {item.label}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="docs-toolbar">
        <label className="docs-search">
          <span>Search documentation</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search titles, keywords and content" />
        </label>
        <button className="button button--light" type="button" onClick={() => void copyLink()}>
          {copied ? "Copied" : "Copy link"}
        </button>
      </div>

      <div className="docs-layout">
        <aside className="docs-tree" aria-label="Documentation sections">
          {Object.entries(categories).map(([category, items]) => (
            <div key={category}>
              <strong>{category}</strong>
              {items.map((item) => (
                <Link className={item.slug === article.slug ? "is-active" : ""} to={`/documentation/${item.slug}`} key={item.slug}>
                  {item.title}
                </Link>
              ))}
            </div>
          ))}
        </aside>

        <article className="docs-article">
          {query.trim() && (
            <section className="docs-results" aria-label="Search results">
              <h2>Search results</h2>
              {results.length === 0 ? (
                <p>No matching articles.</p>
              ) : (
                <div>
                  {results.slice(0, 6).map((result) => (
                    <Link to={`/documentation/${result.article.slug}`} key={result.article.slug}>
                      <strong>{highlight(result.article.title, query)}</strong>
                      <span>{highlight(result.excerpt, query)}</span>
                    </Link>
                  ))}
                </div>
              )}
            </section>
          )}

          <div className="docs-article__header">
            <div>
              <span className="eyebrow">{article.category}</span>
              <h1>{article.title}</h1>
              <p>{article.summary}</p>
            </div>
            <span className="status-badge status-badge--neutral">{language.toUpperCase()}</span>
          </div>
          <MarkdownArticle article={article} />
          <nav className="docs-pagination" aria-label="Article navigation">
            {previous ? <Link to={`/documentation/${previous.slug}`}>Previous: {previous.title}</Link> : <span />}
            {next ? <Link to={`/documentation/${next.slug}`}>Next: {next.title}</Link> : <span />}
          </nav>
        </article>

        <aside className="docs-toc" aria-label="Table of contents">
          <strong>On this page</strong>
          {article.headings.map((heading) => (
            <a href={`#${slugify(heading)}`} key={heading}>{heading}</a>
          ))}
          <strong>Related</strong>
          {article.related.map((related) => {
            const relatedArticle = getArticle(language, related);
            return <Link to={`/documentation/${relatedArticle.slug}`} key={related}>{relatedArticle.title}</Link>;
          })}
        </aside>
      </div>
    </section>
  );
}
