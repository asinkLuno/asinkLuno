"use strict";

function renderFootnotes(html) {
  const definitions = new Map();
  html = html.replace(/<p>(\[\^[\s\S]*?)<\/p>/g, (paragraph, content) => {
    const lines = content.split("<br>");
    if (!lines.every((line) => /^\[\^([\w-]+)\]:\s*/.test(line))) return paragraph;
    lines.forEach((line) => {
      const [, id, text] = line.match(/^\[\^([\w-]+)\]:\s*([\s\S]*)$/);
      definitions.set(id, text);
    });
    return "";
  });

  if (!definitions.size) return html;

  html = html.replace(/\[\^([\w-]+)\]/g, (reference, id) =>
    definitions.has(id)
      ? `<sup id="fnref-${id}"><a href="#fn-${id}">${id}</a></sup>`
      : reference,
  );

  const notes = [...definitions]
    .map(
      ([id, text]) =>
        `<li id="fn-${id}">${text} <a href="#fnref-${id}" aria-label="返回正文">↩</a></li>`,
    )
    .join("");
  return `${html}<section class="footnotes"><hr><ol>${notes}</ol></section>`;
}

if (typeof hexo !== "undefined") {
  hexo.extend.filter.register("after_post_render", (data) => {
    data.content = renderFootnotes(data.content);
    return data;
  });
} else {
  const assert = require("node:assert");
  assert.equal(
    renderFootnotes("<p>正文[^1]</p><p>[^1]: 注释</p>"),
    '<p>正文<sup id="fnref-1"><a href="#fn-1">1</a></sup></p><section class="footnotes"><hr><ol><li id="fn-1">注释 <a href="#fnref-1" aria-label="返回正文">↩</a></li></ol></section>',
  );
}
