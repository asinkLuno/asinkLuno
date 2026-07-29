const { GITMENT_CLIENT_ID, GITMENT_CLIENT_SECRET } = process.env;

if (GITMENT_CLIENT_ID && GITMENT_CLIENT_SECRET) {
  hexo.extend.injector.register(
    "head_end",
    '<link rel="stylesheet" href="https://imsun.github.io/gitment/style/default.css">',
    "post",
  );
  hexo.extend.injector.register(
    "body_end",
    `<div id="comments"></div>
<script src="https://imsun.github.io/gitment/dist/gitment.browser.js"></script>
<script>new Gitment(${JSON.stringify({
      owner: "asinkLuno",
      repo: "asinkLuno",
      oauth: {
        client_id: GITMENT_CLIENT_ID,
        client_secret: GITMENT_CLIENT_SECRET,
      },
    })}).render("comments")</script>`,
    "post",
  );
}
