#!/usr/bin/env python3

import argparse
import hashlib
import json
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = Path("/home/guozr/SynologyDrive/Obsidian/小红书/归档")
POSTS = ROOT / "source" / "_posts"
HAS_CHINESE = re.compile(r"[\u3400-\u9fff]")
REPO = "asinkLuno/asinkLuno"
CATEGORY = "Announcements"


def run(*command: str, capture: bool = False) -> str:
    result = subprocess.run(
        command, cwd=ROOT, check=True, text=True, capture_output=capture
    )
    return result.stdout.strip() if capture else ""


def graphql(query: str, **variables: str) -> dict:
    command = ["gh", "api", "graphql", "-f", f"query={query}"]
    for name, value in variables.items():
        command.extend(("-F", f"{name}={value}"))
    return json.loads(run(*command, capture=True))["data"]


def article(folder: Path) -> Path:
    candidates = [
        path
        for path in folder.glob("*.md")
        if HAS_CHINESE.search(path.stem) and not re.match(r"^\d+_", path.name)
    ]
    exact = [path for path in candidates if path.stem == folder.name]
    if len(exact) == 1:
        return exact[0]
    if len(candidates) == 1:
        return candidates[0]
    raise ValueError(f"{folder.name}: 找到 {len(candidates)} 篇中文 Markdown")


def comment(folder: Path) -> tuple[str, Path]:
    originals = [
        path
        for path in folder.glob("[0-9]*_*.md")
        if not re.search(r"_humanized?\.md$", path.name)
    ]
    if len(originals) != 1:
        raise ValueError(f"{folder.name}: 找到 {len(originals)} 篇编号原稿")
    source = originals[0]
    polished = source.with_name(f"{source.stem}_humanize.md")
    if not polished.exists():
        polished = source.with_name(f"{source.stem}_humanized.md")
    if not polished.exists():
        raise ValueError(f"{folder.name}: 缺少对应的 humanize Markdown")
    return source.name.split("_", 1)[0], polished


def entries(source: Path) -> list[tuple[Path, str, Path]]:
    return [
        (article(folder), *comment(folder))
        for folder in sorted(source.iterdir())
        if folder.is_dir()
    ]


def import_posts(items: list[tuple[Path, str, Path]]) -> None:
    POSTS.mkdir(parents=True, exist_ok=True)
    for source, _, _ in items:
        date = datetime.fromtimestamp(source.stat().st_mtime).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        front_matter = (
            "---\n"
            f"title: {json.dumps(source.stem, ensure_ascii=False)}\n"
            f"date: {date}\n"
            "categories:\n"
            "  - HN复读机\n"
            "---\n\n"
        )
        (POSTS / source.name).write_text(
            front_matter + source.read_text(encoding="utf-8"), encoding="utf-8"
        )


def deploy() -> None:
    run("yarn", "build")
    run(
        "git",
        "add",
        "--",
        "_config.yml",
        "_config.minima.yml",
        "scripts/giscus.js",
        "source/_posts",
        "tools",
    )
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if staged.returncode:
        run(
            "git",
            "commit",
            "-m",
            "feat(blog): publish HN复读机专栏",
            "-m",
            "WHAT: Import archived HN articles and add repeatable publishing automation.\n"
            "WHY: Publish the Chinese articles with their corresponding HN source commentary.\n"
            "HOW: Generate Hexo posts, deploy through GitHub Pages, then create idempotent Giscus discussions and comments.",
        )
        run("git", "push", "origin", "main")

    sha = run("git", "rev-parse", "HEAD", capture=True)
    for _ in range(60):
        runs = json.loads(
            run(
                "gh",
                "run",
                "list",
                "--workflow",
                "pages.yml",
                "--commit",
                sha,
                "--limit",
                "1",
                "--json",
                "databaseId,status,conclusion",
                capture=True,
            )
        )
        if runs and runs[0]["status"] == "completed":
            if runs[0]["conclusion"] != "success":
                raise RuntimeError(f"Pages 部署失败：{runs[0]['conclusion']}")
            return
        time.sleep(5)
    raise TimeoutError("等待 Pages 部署超时")


def publish_comments(items: list[tuple[Path, str, Path]]) -> None:
    owner, name = REPO.split("/")
    data = graphql(
        """
        query($owner:String!, $name:String!) {
          repository(owner:$owner, name:$name) {
            id
            discussionCategories(first:20) { nodes { id name } }
            discussions(first:100) { nodes { id title } }
          }
        }
        """,
        owner=owner,
        name=name,
    )["repository"]
    category_id = next(
        node["id"]
        for node in data["discussionCategories"]["nodes"]
        if node["name"] == CATEGORY
    )
    discussions = {node["title"]: node["id"] for node in data["discussions"]["nodes"]}

    for article_path, hn_id, comment_path in items:
        title = article_path.stem
        discussion_id = discussions.get(title)
        if not discussion_id:
            body = f"# {title}\n\n<!-- sha1: {hashlib.sha1(title.encode()).hexdigest()} -->"
            created = graphql(
                """
                mutation($repo:ID!, $category:ID!, $title:String!, $body:String!) {
                  createDiscussion(input:{
                    repositoryId:$repo, categoryId:$category, title:$title, body:$body
                  }) { discussion { id } }
                }
                """,
                repo=data["id"],
                category=category_id,
                title=title,
                body=body,
            )
            discussion_id = created["createDiscussion"]["discussion"]["id"]

        marker = f"<!-- hn-source: {hn_id} -->"
        body = (
            f"原文链接：https://news.ycombinator.com/item?id={hn_id}\n\n"
            f"{marker}"
        )
        comments = graphql(
            """
            query($id:ID!) {
              node(id:$id) {
                ... on Discussion { comments(first:100) { nodes { id body } } }
              }
            }
            """,
            id=discussion_id,
        )["node"]["comments"]["nodes"]
        existing = next((node for node in comments if marker in node["body"]), None)
        if existing and existing["body"] == body:
            print(f"跳过已有评论：{title}")
            continue
        if existing:
            graphql(
                """
                mutation($id:ID!, $body:String!) {
                  updateDiscussionComment(input:{commentId:$id, body:$body}) {
                    comment { id }
                  }
                }
                """,
                id=existing["id"],
                body=body,
            )
            print(f"已精简评论：{title}")
            continue
        try:
            graphql(
                """
                mutation($discussion:ID!, $body:String!) {
                  addDiscussionComment(input:{discussionId:$discussion, body:$body}) {
                    comment { id }
                  }
                }
                """,
                discussion=discussion_id,
                body=body,
            )
        except subprocess.CalledProcessError:
            comments = graphql(
                """
                query($id:ID!) {
                  node(id:$id) {
                    ... on Discussion { comments(first:100) { nodes { body } } }
                  }
                }
                """,
                id=discussion_id,
            )["node"]["comments"]["nodes"]
            if not any(marker in node["body"] for node in comments):
                raise
        print(f"已发布评论：{title}")


def main() -> None:
    parser = argparse.ArgumentParser(description="上线 HN复读机并发布 Giscus 评论")
    parser.add_argument("source", nargs="?", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    items = entries(args.source)

    if args.dry_run:
        for article_path, hn_id, comment_path in items:
            print(f"{hn_id}\t{article_path.name}\t{comment_path.name}")
        print(f"共 {len(items)} 篇")
        return

    import_posts(items)
    deploy()
    publish_comments(items)


if __name__ == "__main__":
    main()
