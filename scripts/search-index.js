"use strict";

hexo.extend.generator.register("search-index", (locals) => ({
  path: "search.json",
  data: JSON.stringify(
    locals.posts
      .sort("date", "desc")
      .map((post) => ({
        title: post.title,
        url: `${hexo.config.root}${post.path}`,
      })),
  ),
}));

hexo.extend.injector.register(
  "body_end",
  `<script>
    window.addEventListener("load", async () => {
      const input = document.getElementById("search-text");
      const result = document.getElementById("result");
      const posts = await fetch(${JSON.stringify(`${hexo.config.root}search.json`)}).then(
        (response) => response.json(),
      );
      let timer;
      input.oninput = () => {
        clearTimeout(timer);
        timer = setTimeout(() => {
          const query = input.value.trim().toLowerCase();
          result.replaceChildren(
            ...posts
              .filter((post) => query && post.title.toLowerCase().includes(query))
              .map((post) => {
                const link = document.createElement("a");
                link.href = post.url;
                link.textContent = post.title;
                const item = document.createElement("li");
                item.appendChild(link);
                return item;
              }),
          );
        }, 400);
      };
    });
  </script>`,
);
