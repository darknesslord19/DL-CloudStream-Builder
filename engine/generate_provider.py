#!/usr/bin/env python3
# Generate a generic CloudStream Kotlin provider from site config and analysis.
import argparse, json, os, re
from pathlib import Path
from urllib.parse import urlparse

def safe_identifier(s):
    words = re.findall(r'[A-Za-z0-9]+', s or 'GeneratedProvider')
    value = ''.join(w[:1].upper() + w[1:] for w in words) or 'GeneratedProvider'
    if value[0].isdigit(): value = 'Provider' + value
    return value

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--analysis', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    site = os.environ.get('SITE_URL', '').strip()
    plugin_name = os.environ.get('PLUGIN_NAME', 'GeneratedProvider').strip() or 'GeneratedProvider'
    package = os.environ.get('PACKAGE_NAME', 'com.darkneslord.generated').strip()
    content_type = os.environ.get('CONTENT_TYPE', 'movie_tv').strip()
    parsed = urlparse(site)
    if parsed.scheme not in ('http','https') or not parsed.hostname: raise SystemExit('SITE_URL geçersiz')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+', package): raise SystemExit('PACKAGE_NAME geçersiz')
    if content_type not in {'movie_tv','movie','tv','anime','live'}: raise SystemExit('CONTENT_TYPE geçersiz')
    report = json.loads(Path(a.analysis).read_text(encoding='utf-8'))
    base = f'{parsed.scheme}://{parsed.netloc}'
    class_name = safe_identifier(plugin_name)
    types = {'movie': 'setOf(TvType.Movie)', 'tv': 'setOf(TvType.TvSeries)', 'anime': 'setOf(TvType.Anime, TvType.TvSeries)', 'live': 'setOf(TvType.Live)', 'movie_tv': 'setOf(TvType.Movie, TvType.TvSeries, TvType.Anime)'}[content_type]
    # The generated provider uses common public HTML conventions. Per-site selectors can be refined after inspecting the report.
    kotlin = r'''package __PACKAGE__

import android.content.Context
import com.lagradost.cloudstream3.*
import com.lagradost.cloudstream3.utils.*
import org.jsoup.nodes.Document
import org.jsoup.nodes.Element
import java.net.URLEncoder

class __CLASS__Plugin : Plugin() {
    override fun load(context: Context) {
        registerMainAPI(__CLASS__Provider())
    }
}

class __CLASS__Provider : MainAPI() {
    override var mainUrl = "__BASE__"
    override var name = "__NAME__"
    override var lang = "tr"
    override val hasMainPage = true
    override val supportedTypes = __TYPES__

    private val cardSelectors = listOf(
        "article", ".flw-item", ".film-poster", ".movie-item", ".post-item", ".item", ".result-item",
        ".video-item", ".card", ".poster", ".grid-item", "li.wp-manga-chapter"
    )
    private val titleSelectors = listOf(".film-name a", ".entry-title a", ".post-title a", ".title a", "h2 a", "h3 a", "a[title]")
    private val posterSelectors = listOf("img[data-src]", "img[data-lazy-src]", "img[data-original]", ".film-poster img", ".poster img", "img")

    override suspend fun getMainPage(page: Int, request: MainPageRequest): HomePageResponse {
        val pageUrl = if (page <= 1) mainUrl else "$mainUrl/page/$page/"
        val document = app.get(pageUrl).document
        val results = parseCards(document)
        val sections = mutableListOf<HomePageList>()
        if (results.isNotEmpty()) sections.add(HomePageList(if (page <= 1) "Öne Çıkanlar" else "Sayfa $page", results))
        val categoryLinks = document.select("nav a[href], .categories a[href], .category a[href], .cat-links a[href]")
            .mapNotNull { el ->
                val label = el.text().trim()
                val href = fixUrlNull(el.attr("href"))
                if (label.isNotBlank() && href != null && href.startsWith(mainUrl)) label to href else null
            }.distinctBy { it.second }.take(6)
        for ((label, href) in categoryLinks) {
            if (sections.size >= 5) break
            try {
                val categoryDoc = app.get(href).document
                val categoryResults = parseCards(categoryDoc).take(20)
                if (categoryResults.isNotEmpty() && sections.none { it.name.equals(label, true) }) sections.add(HomePageList(label, categoryResults))
            } catch (_: Exception) { }
        }
        return newHomePageResponse(sections, hasNext = results.isNotEmpty())
    }

    override suspend fun search(query: String): List<SearchResponse> {
        val encoded = URLEncoder.encode(query, "UTF-8")
        val candidates = listOf("$mainUrl/?s=$encoded", "$mainUrl/search/$encoded/")
        for (searchUrl in candidates) {
            try {
                val doc = app.get(searchUrl).document
                val results = parseCards(doc)
                if (results.isNotEmpty()) return results
            } catch (_: Exception) { }
        }
        return emptyList()
    }

    private fun parseCards(document: Document): List<SearchResponse> {
        val found = LinkedHashMap<String, SearchResponse>()
        for (selector in cardSelectors) {
            for (card in document.select(selector).take(250)) {
                val titleEl = titleSelectors.asSequence().mapNotNull { card.selectFirst(it) }.firstOrNull()
                    ?: card.selectFirst("a[href][title]")
                    ?: card.selectFirst("a[href]")
                    ?: continue
                val href = fixUrlNull(titleEl.attr("href")) ?: continue
                if (!href.startsWith("http://") && !href.startsWith("https://")) continue
                val title = (titleEl.attr("title").ifBlank { titleEl.text() }).trim().ifBlank { continue }
                val image = posterSelectors.asSequence().mapNotNull { card.selectFirst(it) }.firstOrNull()
                val poster = image?.let { it.attr("data-src").ifBlank { it.attr("data-lazy-src") }.ifBlank { it.attr("data-original") }.ifBlank { it.attr("src") } }?.takeIf { it.isNotBlank() }?.let { fixUrlNull(it) }
                val result = when {
                    supportedTypes.contains(TvType.Anime) && (name.contains("anime", true)) -> newAnimeSearchResponse(title, href, TvType.Anime) { posterUrl = poster }
                    supportedTypes.contains(TvType.TvSeries) && (card.text().contains("bölüm", true) || card.text().contains("season", true) || card.text().contains("episode", true)) -> newTvSeriesSearchResponse(title, href, TvType.TvSeries) { posterUrl = poster }
                    supportedTypes.contains(TvType.Movie) -> newMovieSearchResponse(title, href, TvType.Movie) { posterUrl = poster }
                    supportedTypes.contains(TvType.TvSeries) -> newTvSeriesSearchResponse(title, href, TvType.TvSeries) { posterUrl = poster }
                    else -> newMovieSearchResponse(title, href, TvType.Movie) { posterUrl = poster }
                }
                if (href.startsWith(mainUrl)) found.putIfAbsent(href, result)
            }
            if (found.size >= 15) break
        }
        return found.values.toList()
    }

    override suspend fun load(url: String): LoadResponse? {
        val document = app.get(url).document
        val title = document.selectFirst("h1, .entry-title, .film-name, .movie-title")?.text()?.trim()
            ?.takeIf { it.isNotBlank() } ?: document.title().substringBefore(" - ").trim().ifBlank { return null }
        val posterEl = document.selectFirst("meta[property=og:image]")
        val poster = posterEl?.attr("content")?.let { fixUrlNull(it) }
            ?: document.selectFirst(".poster img, .film-poster img, article img, .entry-content img")?.let { img ->
                img.attr("data-src").ifBlank { img.attr("data-lazy-src") }.ifBlank { img.attr("data-original") }.ifBlank { img.attr("src") }.takeIf { it.isNotBlank() }?.let { fixUrlNull(it) }
            }
        val plot = document.selectFirst("meta[name=description]")?.attr("content")?.takeIf { it.isNotBlank() }
            ?: document.selectFirst(".description, .plot, .entry-content, .summary")?.text()?.take(2000)
        val episodeElements = document.select(".episodes a[href], .episode-list a[href], a[href*=bolum], a[href*=episode], a[href*=episod]")
            .filter { it.attr("href").startsWith("http") || it.attr("href").startsWith("/") }
            .distinctBy { fixUrl(it.attr("href")) }
        val isSeries = "__CONTENT_TYPE__" == "tv" || "__CONTENT_TYPE__" == "anime" || ("__CONTENT_TYPE__" == "movie_tv" && episodeElements.isNotEmpty())
        if (isSeries) {
            val episodes = episodeElements.mapIndexed { index, el ->
                val href = fixUrl(el.attr("href"))
                val label = el.text().trim().ifBlank { "Bölüm ${index + 1}" }
                val epNo = Regex("(?i)(?:bölüm|bolum|episode|ep)\\s*[-:#.]?\\s*(\\d+)").find(label)?.groupValues?.getOrNull(1)?.toIntOrNull() ?: (index + 1)
                newEpisode(href) { name = label; episode = epNo }
            }
            return newTvSeriesLoadResponse(title, url, if (__CONTENT_TYPE__ == "anime") TvType.Anime else TvType.TvSeries, episodes) {
                posterUrl = poster
                this.plot = plot
            }
        }
        return newMovieLoadResponse(title, url, TvType.Movie, url) {
            posterUrl = poster
            this.plot = plot
        }
    }

    override suspend fun loadLinks(
        data: String,
        isCasting: Boolean,
        subtitleCallback: (SubtitleFile) -> Unit,
        callback: (ExtractorLink) -> Unit
    ): Boolean {
        var found = false
        val doc = try { app.get(data).document } catch (_: Exception) { return false }
        val candidates = LinkedHashSet<String>()
        doc.select("iframe[src], video[src], source[src], a[href]").forEach { el ->
            val raw = when (el.tagName()) {
                "iframe", "video", "source" -> el.attr("src")
                else -> el.attr("href")
            }
            if (raw.isBlank()) return@forEach
            val href = fixUrl(raw)
            if (href.startsWith(mainUrl) || href.matches(Regex("(?i)^https?://.+\\.(m3u8|mpd|mp4|webm)(?:[?#].*)?$"))) candidates.add(href)
        }
        for (candidate in candidates.take(30)) {
            try {
                loadExtractor(candidate, data, subtitleCallback, callback)
                found = true
            } catch (_: Exception) { }
        }
        return found
    }
}
'''
    for old,new in {'__PACKAGE__':package,'__CLASS__':class_name,'__BASE__':base,'__NAME__':plugin_name.replace('\\','\\\\').replace('"','\\"'),'__TYPES__':types,'__CONTENT_TYPE__':content_type}.items(): kotlin=kotlin.replace(old,new)
    out=Path(a.out)/package.replace('.','/')
    out.mkdir(parents=True, exist_ok=True)
    dest=out/f'{class_name}Provider.kt'
    dest.write_text(kotlin, encoding='utf-8')
    # machine-readable generation metadata for debugging/audit
    meta={'plugin_name':plugin_name,'package_name':package,'class_name':class_name,'site_url':base,'content_type':content_type,'pages_analyzed':report.get('pagesParsed',0),'wordpress_detected':report.get('wordpressDetected',False),'generated_source':str(dest)}
    Path('build').mkdir(exist_ok=True)
    Path('build/provider-generation.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(meta,ensure_ascii=False))

if __name__ == '__main__': main()
